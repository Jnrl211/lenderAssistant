from email.message import EmailMessage
from getpass import getpass
import logging
import os
from random import randint
import smtplib
from textwrap import dedent
import time
from typing import Optional

from dotenv import load_dotenv
from playwright.sync_api import BrowserContext, ElementHandle, Page, sync_playwright

from requisitions import Destination, DetailedFilter, DetailedRequisition, Education, Filter, Grade, Housing, OccupationType, Requisition


# Load environment variables from .env file in the same directory as this script.
load_dotenv(
    os.path.join(os.path.dirname(__file__), ".env")
)


# Logs have been optimized to use lazy evaluation instead of f-strings in logs.
# This way, log messages are not evaluated until they are actually logged.
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(filename)s] [%(funcName)s] %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def maximize_chromium_window(context: BrowserContext, page: Page):
    """Maximize a Chromium browser window from Playwright.

    Creates a CDP (Chrome DevTools Protocol) session and sends commands to the browser
    window to maximize it and set the viewport to the window dimensions, since Playwright
    has no built-in way to do this.

    * Chromium is used instead of Firefox because it is the only browser
    that supports maximizing the window via CDP with Playwright.

    Arguments:
    - context: The `BrowserContext` object to use to interact with the browser.
    - page: The `Page` object to use to interact with the page.
    """
    session = context.new_cdp_session(page)
    try:
        window_handle = session.send("Browser.getWindowForTarget")
        window_id = window_handle["windowId"]
        session.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {"windowState": "maximized"}
        })
        bounds = session.send("Browser.getWindowBounds", {"windowId": window_id})
        if "bounds" in bounds:
            # 1920 and 1080 are fallback values in case of error.
            size = bounds["bounds"]
            width = size.get("width", 1920)
            height = size.get("height", 1080)
            # Viewport size is changed before and after maximizing because maximizing
            # only expands the window frame, not the content. Before: maximizing expands
            # the window to screen size, so we need those dimensions to set the viewport.
            # After: setting the viewport size restores (un-maximizes) the window.
            page.set_viewport_size({"width": width, "height": height})
            # Maximize again after setting viewport size, since that restores the window.
            session.send("Browser.setWindowBounds", {
                "windowId": window_id,
                "bounds": {"windowState": "maximized"}
            })
    finally:
        # Detach the session to avoid keeping it open past this call and leaking memory.
        session.detach()


def launch_maximized_chromium():
    """Launches a maximized Chromium browser window using Playwright.

    Returns the browser and page objects.
    """
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=False, 
        args=[
            "--window-position=0,0"  # Top-left corner.
        ]
    )
    # Use a large viewport to emulate maximized window.
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    maximize_chromium_window(context, page)
    return playwright, browser, context, page


def log_in(page: Page, manual_password: Optional[str] = None):
    """Logs in to the platform using the e-mail and password defined in the .env file,
    or a password provided by user input.
    
    Arguments:
    - page: The page object to use to interact with the platform.
    - manual_password: The password to use to log in. If not provided, the password defined in the .env file will be used.
    """
    SIGN_IN_URL = os.getenv("SIGN_IN_URL").strip()
    ACCOUNT_EMAIL = os.getenv("ACCOUNT_EMAIL").strip()
    ACCOUNT_PASSWORD = os.getenv("ACCOUNT_PASSWORD").strip()
    page.goto(SIGN_IN_URL)
    page.wait_for_selector("#email")
    page.click("#email")
    page.fill("#email", ACCOUNT_EMAIL)
    time.sleep(randint(5, 10))  # Cooldown to avoid detection.
    page.wait_for_selector("//*[@id='email']/parent::*/parent::form/button[@type='submit'][last()]")
    page.click("//*[@id='email']/parent::*/parent::form/button[@type='submit'][last()]")
    time.sleep(randint(5, 10))  # Cooldown to avoid detection.
    page.click("#password")
    page.fill("#password", ACCOUNT_PASSWORD)
    if manual_password is not None:
        page.fill("#password", manual_password)
    time.sleep(randint(5, 10))  # Cooldown to avoid detection.
    page.wait_for_selector("//*[@id='password']/parent::*/parent::form/button[@type='submit'][last()]")
    page.click("//*[@id='password']/parent::*/parent::form/button[@type='submit'][last()]")
    time.sleep(randint(5, 10))  # Cooldown to avoid detection.
    # Waits until the requisition table is found, raise exception if not found.
    page.wait_for_selector("#requisitions")


def fetch_basic_requisition_list(page: Page) -> list[Requisition]:
    """Fetches the requisition list from the platform,
    collecting only available basic requisition data in `Requisition` objects.

    To collect details for a full `DetailedRequisition` list,
    the data from each `Requisition` must be scraped individually from its own requisition page.

    Returns a list containing all the collected `Requisition` objects.

    Arguments:
    - page: The `Page` object to use to interact with the page.
    """
    REQUISITION_BASE_URL = os.getenv("REQUISITION_BASE_URL").strip()
    # Wait for the first requisition row to appear.
    page.wait_for_selector("#requisitions > div[role='button']")
    rows = page.query_selector_all("#requisitions > div[role='button']")
    logger.info("Found %s rows in the requisition list.", len(rows))
    requisitions: list[Requisition] = []
    for index, row in enumerate(rows):
        logger.info("Collecting basic requisition data for row %s of %s.", (index + 1), len(rows))

        # Collect basic requisition data.
        # The loan number is located in the first child element of the row,
        # to get the number only, the trailing ordinal symbol (º) must be removed,
        # this symbol is also used to check whether the bubble contains the loan number,
        # and not other data (this edge case has occurred before).
        loan_number = row.query_selector("div:nth-child(1) span span")
        if loan_number is not None and loan_number.text_content().find("º") != -1:
            loan_number = int(loan_number.text_content()[:-1].strip())
        else:
            loan_number = 1
        requisition_id = row.query_selector("p:nth-child(2) span").text_content()
        requisition_id = requisition_id.strip()
        requisition_url = f"{REQUISITION_BASE_URL}/{requisition_id}"
        grade = row.query_selector("p:nth-child(3) b:nth-child(1)").text_content()
        grade = Grade[grade.strip()]
        # Remove leading "/ " and trailing "%" sequences to get the interest rate in percentage form.
        interest_rate = row.query_selector("p:nth-child(3) b:nth-child(2)").text_content()
        interest_rate = float(interest_rate.replace("/ ", "").replace("%", "").strip()) / 100
        score = row.query_selector("p:nth-child(4)").text_content()
        score = int(score.strip())
        destination = row.query_selector("div:nth-child(5) p:nth-child(2)").text_content()
        destination = Destination(destination.strip())
        term = row.query_selector("p:nth-child(6)").text_content()
        term = int(term.strip())
        # Remove leading "$" and "," sequences to get the amount in MXN from currency format.
        amount = row.query_selector("p:nth-child(7)").text_content()
        amount = float(amount.replace("$", "").replace(",", "").strip())
        remaining_funding_amount = row.query_selector("p:nth-child(8)").text_content()
        remaining_funding_amount = float(remaining_funding_amount.replace("$", "").replace(",", "").strip())
        
        # Log requisition data in order.
        logger.debug("- ID: %s", requisition_id)
        logger.debug("- URL: %s", requisition_url)
        logger.debug("- Grade: %s", grade)
        logger.debug("- Interest rate: %s%%", interest_rate * 100)
        logger.debug("- Score: %s", score)
        logger.debug("- Destination: %s", destination.value)
        logger.debug("- Term: %s months", term)
        logger.debug("- Amount: %s MXN", amount)
        logger.debug("- Remaining funding amount: %s MXN", remaining_funding_amount)
        logger.debug("- Loan number: %s", loan_number)

        requisition = Requisition(
            id=requisition_id,
            url=requisition_url,
            grade=grade,
            interest_rate=interest_rate,
            score=score,
            destination=destination,
            term=term,
            amount=amount,
            remaining_funding_amount=remaining_funding_amount,
            loan_number=loan_number
        )
        requisitions.append(requisition)
    return requisitions


def select_by_basic_filters(requisitions: list[Requisition], filters: list[Filter]) -> list[Requisition]:
    """Performs filtering of a list of requisitions based on basic requisition criteria.
    
    Includes requisitions that meet at least one of the filters, whitelist behavior.

    Arguments:
    - requisitions: The list of requisitions to filter.
    - filters: The list of basic filters to apply to the requisitions.
    """
    filtered_requisitions: list[Requisition] = []
    for requisition in requisitions:
        meets_any_filter: bool = False
        for filter in filters:
            if requisition.meets_filter(filter):
                meets_any_filter = True
                break
        if not meets_any_filter:
            continue
        filtered_requisitions.append(requisition)
    return filtered_requisitions


def fetch_requisition_details(context: BrowserContext, requisition: Requisition):
    """Fetches the details of a requisition from the platform.

    Arguments:
    - page: The page object to use to interact with the platform.
    - requisition: The requisition to fetch the details of.
    """
    logger.info("Obtaining requisition details for requisition %s.", requisition.id)

    # Add a new-tab to open the requisition page, and then close it after fetching the details.
    new_page = context.new_page()
    new_page.goto(requisition.url)

    # Get monthly payment data.
    new_page.wait_for_selector(".groupItems")
    # There are 4 elements to fetch here, and they are not identical.
    monthly_payment_boxes = new_page.query_selector_all(".groupItems > div")
    monthly_payment = monthly_payment_boxes[3].query_selector("div:nth-child(2) > p").text_content()
    # Remove leading "$" and "," sequences to get the amount in MXN.
    monthly_payment = float(monthly_payment.replace("$", "").replace(",", "").strip())

    # Get financial status data.
    # These are selected with XPATH instead of CSS selectors because their class names are randomized.
    new_page.wait_for_selector("//p[text()='Ingresos']/preceding-sibling::p")
    total_income = new_page.query_selector("//p[text()='Ingresos']/preceding-sibling::p")
    total_income = float(total_income.text_content().replace("$", "").replace(",", "").strip())
    new_page.wait_for_selector("//p[text()='Egresos']/preceding-sibling::p")
    total_expenses = new_page.query_selector("//p[text()='Egresos']/preceding-sibling::p")
    total_expenses = float(total_expenses.text_content().replace("$", "").replace(",", "").strip())

    # Get credit history data.
    new_page.wait_for_selector(".container")
    credit_history_boxes = new_page.query_selector_all(".container > div")
    # The score is already fetched from the requisition list, it's unnecessary to extract it here.
    score = credit_history_boxes[0].query_selector("div > div > h4").text_content()
    score = int(score.strip())
    credit_history_length = credit_history_boxes[1].query_selector("div > div > h4").text_content()
    credit_history_length = int(credit_history_length.strip())
    credit_history_inquiries = credit_history_boxes[2].query_selector("div > div > h4").text_content()
    credit_history_inquiries = int(credit_history_inquiries.strip())
    opened_accounts = credit_history_boxes[3].query_selector("div > div > h4").text_content()
    opened_accounts = int(opened_accounts.strip())

    # Get personal information data.
    new_page.wait_for_selector(".personalInfo")
    personal_information_boxes = new_page.query_selector_all(".personalInfo > div > div:nth-child(2) > div")
    age = personal_information_boxes[0].query_selector("p:nth-child(2)").text_content()
    age = int(age.strip())
    dependents = personal_information_boxes[1].query_selector("p:nth-child(2)").text_content()
    dependents = int(dependents.strip())
    has_major_medical_insurance = personal_information_boxes[2].query_selector("p:nth-child(2)").text_content()
    has_major_medical_insurance = has_major_medical_insurance.strip().lower()
    if has_major_medical_insurance == "si":
        has_major_medical_insurance = True
    elif has_major_medical_insurance == "no":
        has_major_medical_insurance = False
    else:
        raise ValueError(f"Invalid value for has_major_medical_insurance: {has_major_medical_insurance}")
    has_own_vehicle = personal_information_boxes[3].query_selector("p:nth-child(2)").text_content()
    has_own_vehicle = has_own_vehicle.strip().lower()
    if has_own_vehicle == "si":
        has_own_vehicle = True
    elif has_own_vehicle == "no":
        has_own_vehicle = False
    else:
        raise ValueError(f"Invalid value for has_own_vehicle: {has_own_vehicle}")
    education = personal_information_boxes[4].query_selector("p:nth-child(2)").text_content()
    education = Education.parse_from_label(education)

    # TODO: update this when, or if I make an Enum for state of residence.

    state_of_residence = personal_information_boxes[5].query_selector("p:nth-child(2)").text_content()
    state_of_residence = state_of_residence.strip().lower().capitalize()
    housing = personal_information_boxes[6].query_selector("p:nth-child(2)").text_content()
    housing = Housing(housing)
    occupation = personal_information_boxes[7].query_selector("p:nth-child(2)").text_content()
    occupation = occupation.strip()
    # This is usually found as "<number> años", so by splitting the string at the first space,
    # the number of years can be obtained in the first element of the split.
    tenure = personal_information_boxes[8].query_selector("p:nth-child(2)").text_content()
    tenure = int(tenure.split(" ", 1)[0].strip())
    occupation_type = personal_information_boxes[9].query_selector("p:nth-child(2)").text_content()
    occupation_type = OccupationType(occupation_type.strip().lower().capitalize())

    # Get shareholder list data.
    # This check is intended to detect if the platform is a shareholder in the requisition,
    # and shares some of the risk with the investor,
    # requisitions that meet this criteria are considered safer for investment.
    # Wait for the shareholders tab to appear,
    # this is done because the note loads in the DOM only after clicking the shareholders tab.
    new_page.wait_for_selector(".react-tabs > ul > li:nth-child(2)")
    new_page.click(".react-tabs > ul > li:nth-child(2)")
    # Wait for the "risk share by platform" note to appear.
    # The timeout is set to something short, because the note should appear almost immediately when present.
    # Wrapped in try-except to handle the exception thrown when the note is not present.
    is_platform_in_shareholder_list: Optional[ElementHandle] = None
    try:
        is_platform_in_shareholder_list = new_page.wait_for_selector("div.borrowers > div.ytp-note", timeout=3000)
    except Exception as e:
        pass
    if is_platform_in_shareholder_list is not None:
        is_platform_in_shareholder_list = True
    else:
        is_platform_in_shareholder_list = False

    # Log collected data.
    logger.debug("  [  Financial status data  ]")
    logger.debug("- Monthly payment: %s", monthly_payment)
    logger.debug("- Total income: %s", total_income)
    logger.debug("- Total expenses: %s", total_expenses)
    logger.debug("  [  Credit history data  ]")
    logger.debug("- Score: %s", score)
    logger.debug("- Credit history length (years): %s", credit_history_length)
    logger.debug("- Credit history inquiries: %s", credit_history_inquiries)
    logger.debug("- Opened accounts: %s", opened_accounts)
    logger.debug("  [  Personal information data  ]")
    logger.debug("- Age (years): %s", age)
    logger.debug("- Dependents: %s", dependents)
    logger.debug("- Has major medical insurance: %s", has_major_medical_insurance)
    logger.debug("- Has own vehicle: %s", has_own_vehicle)
    logger.debug("- Education: %s", education.name)
    logger.debug("- State of residence: %s", state_of_residence)
    logger.debug("- Housing: %s", housing.name)
    logger.debug("- Occupation (may be empty string): %s", occupation)
    logger.debug("- Tenure (years): %s", tenure)
    logger.debug("- Occupation type: %s", occupation_type.name)
    logger.debug("  [  Shareholder list data  ]")
    logger.debug("- Is platform in shareholder list: %s", is_platform_in_shareholder_list)

    # Cooldown before and after closing the page to avoid bot detection, and do browser cleanup.
    time.sleep(randint(5, 10))
    new_page.close()
    time.sleep(randint(5, 10))

    return DetailedRequisition(
        base_requisition=requisition,
        monthly_payment=monthly_payment,
        credit_history_length=credit_history_length,
        credit_history_inquiries=credit_history_inquiries,
        opened_accounts=opened_accounts,
        total_income=total_income,
        total_expenses=total_expenses,
        age=age,
        dependents=dependents,
        has_major_medical_insurance=has_major_medical_insurance,
        has_own_vehicle=has_own_vehicle,
        education=education,
        state_of_residence=state_of_residence,
        housing=housing,
        occupation=occupation,
        tenure=tenure,
        occupation_type=occupation_type,
        is_platform_in_shareholder_list=is_platform_in_shareholder_list
    )


def select_by_detailed_filters(
    context: BrowserContext,
    requisitions: list[Requisition],
    filters: list[DetailedFilter]
) -> list[DetailedRequisition]:
    """Selects requisitions that meet at least one of the detailed filters.
    
    Arguments:
    - context: The `BrowserContext` object to use to interact with the platform.
    - requisitions: The list of basic requisitions to filter.
    - filters: The list of detailed filters to apply to the requisitions.
    """
    filtered_requisitions: list[DetailedRequisition] = []
    for requisition in requisitions:
        detailed_requisition: DetailedRequisition
        try:
            detailed_requisition = fetch_requisition_details(context=context, requisition=requisition)
        except Exception as e:
            logger.exception("Failed to fetch the details of requisition %s: %s", requisition.id, e)
            try:
                send_failed_detailed_requisition_fetch_email(requisition=requisition)
            except Exception as email_e:
                logger.exception("Failed to send e-mail notification of failed detailed requisition fetch of requisition %s: %s", requisition.id, email_e)
            raise e
        meets_any_filter: bool = False
        for filter in filters:
            if detailed_requisition.meets_filter(filter):
                meets_any_filter = True
                break
        if not meets_any_filter:
            continue
        filtered_requisitions.append(detailed_requisition)
    return filtered_requisitions


def send_email_message(message: EmailMessage):
    """Sends an e-mail message to a fixed list of recipients,
    predefined in environment variables.
    
    This function is intended to simplify e-mail sending operations,
    and reduce code duplication.

    The message must be prepared with the subject, simple content,
    alternative content and attachments beforehand.
    Correspondence details are prepared in this function.

    Arguments:
    - message: The e-mail message to send.
    """
    # Prepare e-mail message correspondence details.
    TO_RECIPIENTS = os.getenv("SMTP_TO_RECIPIENTS", "").split(",")
    CC_RECIPIENTS = os.getenv("SMTP_CC_RECIPIENTS", "").split(",")
    BCC_RECIPIENTS = os.getenv("SMTP_BCC_RECIPIENTS", "").split(",")
    # Remove duplicates by unpacking the recipient lists into a set,
    # then unpack the set into a list to use in send_message.
    ALL_RECIPIENTS = [*{*TO_RECIPIENTS, *CC_RECIPIENTS, *BCC_RECIPIENTS}]
    message["From"] = os.getenv("SMTP_USER")
    message["To"] = TO_RECIPIENTS
    message["Cc"] = CC_RECIPIENTS
    message["Bcc"] = BCC_RECIPIENTS

    # Send e-mail message.
    with smtplib.SMTP_SSL(
        host=os.getenv("SMTP_HOST"),
        port=int(os.getenv("SMTP_PORT")),
        timeout=60
    ) as smtp_server:
        smtp_server.login(
            user=os.getenv("SMTP_USER"),
            password=os.getenv("SMTP_PASSWORD")
        )
        smtp_server.send_message(
            msg=message,
            from_addr=os.getenv("SMTP_USER"),
            to_addrs=ALL_RECIPIENTS
        )


def send_eligible_requisition_list_email(requisitions: list[DetailedRequisition]):
    """Sends a list of eligible `DetailedRequisition` requisitions by e-mail.
    
    Arguments:
    - requisitions: The list of eligible `DetailedRequisition` requisitions to send by e-mail.
    """
    # Prepare e-mail message content.
    # Backslash at the start removes the first newline character in multiline strings,
    # and dedent() removes the common indentation (of code formatting) from them.
    simple_content = dedent(f"""\
        Eligible requisitions for investment

        The following requisitions have been identified as eligible for investment:

        {f"{os.linesep}".join(
            [f"- {requisition.id}" for requisition in requisitions]
        )}
    """)
    requisition_list_html = []
    for requisition in requisitions:
        shareholder_label: str
        if requisition.is_platform_in_shareholder_list == True:
            shareholder_label = "Yes"
        elif requisition.is_platform_in_shareholder_list == False:
            shareholder_label = "No"
        else:
            raise ValueError(f"Invalid value for 'is_platform_in_shareholder_list' in requisition {requisition.id}: {requisition.is_platform_in_shareholder_list}")
        list_item_html = dedent(f"""\
            <li>
                <ul>
                    <li><strong>ID:</strong> {requisition.id}</li>
                    <li><strong>URL:</strong> {requisition.url}</li>
                    <li><strong>Grade:</strong> {requisition.grade.name}</li>
                    <li><strong>Interest rate:</strong> {requisition.interest_rate * 100}%</li>
                    <li><strong>Score:</strong> {requisition.score}</li>
                    <li><strong>Destination:</strong> {requisition.destination.value}</li>
                    <li><strong>Term:</strong> {requisition.term} months</li>
                    <li><strong>Amount:</strong> {requisition.amount:,.2f} MXN</li>
                    <li><strong>Remaining funding amount:</strong> {requisition.remaining_funding_amount:,.2f} MXN</li>
                    <li><strong>Loan number:</strong> {requisition.loan_number}</li>
                    <li><strong>Monthly payment:</strong> {requisition.monthly_payment:,.2f} MXN</li>
                    <li><strong>Credit history length:</strong> {requisition.credit_history_length} years</li>
                    <li><strong>Credit history inquiries:</strong> {requisition.credit_history_inquiries}</li>
                    <li><strong>Opened accounts:</strong> {requisition.opened_accounts}</li>
                    <li><strong>Total income:</strong> {requisition.total_income:,.2f} MXN</li>
                    <li><strong>Total expenses:</strong> {requisition.total_expenses:,.2f} MXN</li>
                    <li><strong>Age:</strong> {requisition.age}</li>
                    <li><strong>Dependents:</strong> {requisition.dependents}</li>
                    <li><strong>Has major medical insurance:</strong> {"Yes" if requisition.has_major_medical_insurance else "No"}</li>
                    <li><strong>Has own vehicle:</strong> {"Yes" if requisition.has_own_vehicle else "No"}</li>
                    <li><strong>Education:</strong> {requisition.education.name.capitalize()}</li>
                    <li><strong>State of residence:</strong> {requisition.state_of_residence}</li>
                    <li><strong>Housing:</strong> {requisition.housing.name.capitalize()}</li>
                    <li><strong>Occupation:</strong> {requisition.occupation}</li>
                    <li><strong>Tenure:</strong> {requisition.tenure} years</li>
                    <li><strong>Occupation type:</strong> {requisition.occupation_type.name.capitalize()}</li>
                    <li><strong>Is platform in shareholder list:</strong> {shareholder_label}</li>
                </ul>
            </li>
        """)
        requisition_list_html.append(list_item_html)
    requisition_list_html = f"{os.linesep}".join(requisition_list_html)
    alternative_content = dedent(f"""\
        <html>
            <body>
                <h1>Eligible requisitions for investment</h1>
                <p>The following requisitions have been identified as eligible for investment:</p>
                <ul>
                    {requisition_list_html}
                </ul>
            </body>
        </html>
    """)

    # Prepare and send e-mail message.
    message = EmailMessage()
    message["Subject"] = "[BOT] [lender-assistant] Eligible requisition list update"
    message.set_content(simple_content)
    message.add_alternative(
        alternative_content,
        subtype="html"
    )
    send_email_message(message=message)


# Functions for error reporting over e-mail when the bot crashes on data scraping operations,
# so I am notified when the bot requires an update to match the platform frontend changes.
def send_failed_login_email():
    """Sends an e-mail notifying that the bot failed at the step of logging in to the platform."""
    # Prepare e-mail message content.
    simple_content = dedent(f"""\
        Your attention is required.

        The bot failed to log in to the platform and could not complete the process.

        If the platform frontend has changed, an update to the bot may be necessary to resume operation.
    """)
    alternative_content = dedent(f"""\
        <html>
            <body>
                <h1>Your attention is required.</h1>
                <p>The bot failed to <strong>log in to the platform</strong> and could not complete the process.</p>
                <p>If the platform frontend has changed, <strong>an update to the bot may be necessary</strong> to resume operation.</p>
            </body>
        </html>
    """)

    # Prepare and send e-mail message.
    message = EmailMessage()
    message["Subject"] = "[BOT] [lender-assistant] [ERROR] Failed to log in to the platform"
    message.set_content(simple_content)
    message.add_alternative(
        alternative_content,
        subtype="html"
    )
    send_email_message(message=message)


def send_failed_basic_requisition_list_fetch_email():
    """Sends an e-mail notifying that the bot failed at the step of fetching the basic requisition list."""
    # Prepare e-mail message content.
    simple_content = dedent(f"""\
        Your attention is required.

        The bot failed to fetch the basic requisition list and could not complete the process.

        If the platform frontend has changed, an update to the bot may be necessary to resume operation.
    """)
    alternative_content = dedent(f"""\
        <html>
            <body>
                <h1>Your attention is required.</h1>
                <p>The bot failed to <strong>fetch the basic requisition list</strong> and could not complete the process.</p>
                <p>If the platform frontend has changed, <strong>an update to the bot may be necessary</strong> to resume operation.</p>
            </body>
        </html>
    """)

    # Prepare and send e-mail message.
    message = EmailMessage()
    message["Subject"] = "[BOT] [lender-assistant] [ERROR] Failed to fetch the basic requisition list"
    message.set_content(simple_content)
    message.add_alternative(
        alternative_content,
        subtype="html"
    )
    send_email_message(message=message)


def send_failed_detailed_requisition_fetch_email(requisition: Requisition):
    """Sends an e-mail notifying that the bot failed at the step of fetching the details of a basic requisition.
    
    Arguments:
    - requisition: The `Requisition` object on which the bot failed to fetch the details.
    """
    # Prepare e-mail message content.
    simple_content = dedent(f"""\
        Your attention is required.

        The bot failed to fetch the details of requisition with ID {requisition.id} and could not complete the process.

        If the platform frontend has changed, an update to the bot may be necessary to resume operation.
    """)
    alternative_content = dedent(f"""\
        <html>
            <body>
                <h1>Your attention is required.</h1>
                <p>The bot failed to <strong>fetch the details of requisition with ID {requisition.id}</strong> and could not complete the process.</p>
                <p>If the platform frontend has changed, <strong>an update to the bot may be necessary</strong> to resume operation.</p>
            </body>
        </html>
    """)

    # Prepare and send e-mail message.
    message = EmailMessage()
    message["Subject"] = f"[BOT] [lender-assistant] [ERROR] Failed to fetch the details of requisition with ID {requisition.id}"
    message.set_content(simple_content)
    message.add_alternative(
        alternative_content,
        subtype="html"
    )
    send_email_message(message=message)


if __name__ == "__main__":
    # Read configuration from file.
    filters: list[Filter] = Filter.parse_all_from_yaml(
        path=os.path.join(os.path.dirname(__file__), "config.yml")
    )
    detailed_filters: list[DetailedFilter] = DetailedFilter.parse_all_from_yaml(
        path=os.path.join(os.path.dirname(__file__), "config.yml")
    )

    # Request manual password input if not provided in the environment variables.
    manual_password = None
    if os.getenv("ACCOUNT_PASSWORD", "") == "":
        manual_password = getpass("Enter your password: ")

    # Launch and prepare browser window.
    playwright, browser, context, page = launch_maximized_chromium()

    # Log in to the platform.
    try:
        log_in(page, manual_password)
    except Exception as e:
        logger.exception("Failed to log in to the platform: %s", e)
        try:
            send_failed_login_email()
        except Exception as email_e:
            logger.exception("Failed to send e-mail notification of failed login: %s", email_e)
        raise e
    logger.info("Logged in to the platform successfully.")

    # Fetch the basic requisition list.
    requisitions: list[Requisition]
    try:
        requisitions = fetch_basic_requisition_list(page)
    except Exception as e:
        logger.exception("Failed to fetch the basic requisition list: %s", e)
        try:
            send_failed_basic_requisition_list_fetch_email()
        except Exception as email_e:
            logger.exception("Failed to send e-mail notification of failed basic requisition list fetch: %s", email_e)
        raise e
    logger.info("Fetched the basic requisition list successfully.")

    # Filter the requisition list with basic filters.
    filtered_requisitions = select_by_basic_filters(requisitions, filters)
    logger.info("Found %s requisitions meeting at least one of the basic filters.", len(filtered_requisitions))
    for requisition in filtered_requisitions:
        logger.debug("- ID: %s", requisition.id)
        logger.debug("- URL: %s", requisition.url)
        logger.debug("- Grade: %s", requisition.grade)
        logger.debug("- Interest rate: %s%%", requisition.interest_rate)
        logger.debug("- Score: %s", requisition.score)
        logger.debug("- Destination: %s", requisition.destination.value)
        logger.debug("- Term: %s months", requisition.term)
        logger.debug("- Amount: %s MXN", requisition.amount)
        logger.debug("- Remaining funding amount: %s MXN", requisition.remaining_funding_amount)
        logger.debug("- Loan number: %s", requisition.loan_number)
    logger.info("Filtered the requisition list with basic filters successfully.")

    # Filter basic requisitions by detailed filters.
    detailed_requisitions = select_by_detailed_filters(
        context=context,
        requisitions=filtered_requisitions,
        filters=detailed_filters
    )
    logger.info("Found %s detailed requisitions meeting at least one of the detailed filters.", len(detailed_requisitions))
    for requisition in detailed_requisitions:
        logger.info("- ID: %s", requisition.id)
    logger.info("Filtered the requisition list with detailed filters successfully.")

    # Send eligible requisition list e-mail.
    try:
        send_eligible_requisition_list_email(requisitions=detailed_requisitions)
    except Exception as e:
        logger.exception("Failed to send eligible requisition list e-mail: %s", e)
        raise e
    logger.info("Sent eligible requisition list e-mail successfully.")

    context.close()
    playwright.stop()
