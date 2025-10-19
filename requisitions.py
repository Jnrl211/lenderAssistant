from __future__ import annotations
from enum import Enum, IntEnum, auto
import inspect
from typing import Any, Self

from yaml import safe_load


class Grade(IntEnum):
    """Requisition risk grades enumeration.

    A1 is the grade with the lowest risk of default and the lowest interest rate, 
    C7 is the grade with the highest risk of default and the highest interest rate.

    Each grade is assigned an incremental integer value so they can be sorted by risk level.

    Extends `IntEnum` instead of `Enum` to include built-in ordering and comparison methods, and allow comparing members as integers.
    """

    A1 = 0
    A2 = auto()
    A3 = auto()
    A4 = auto()
    A5 = auto()
    A6 = auto()
    A7 = auto()
    B1 = auto()
    B2 = auto()
    B3 = auto()
    B4 = auto()
    B5 = auto()
    B6 = auto()
    B7 = auto()
    C1 = auto()
    C2 = auto()
    C3 = auto()
    C4 = auto()
    C5 = auto()
    C6 = auto()
    C7 = auto()


class Destination(Enum):
    """Requisition destination enumeration.

    Indicates the alleged destination of the loan requisition, according to the requisitioner. 

    For subjective evaluation and filtering.
    """

    FAMILY = "Familiar"
    PAY_DEBTS = "Pagar Deudas"
    CAR = "Automóvil"
    BUSINESS = "Negocio"
    EDUCATION = "Educación"
    HOUSING = "Vivienda"
    PERSONAL_EXPENSES = "Gastos Personales"


class Requisition():
    """A `Requisition` contains basic information about a requisition, collected from the requisition list page."""

    id: str
    url: str
    grade: Grade
    interest_rate: float  # Stored as percentage value (not decimal form).
    score: int
    destination: Destination
    term: int  # Loan term in months.
    amount: float  # Requisition amount in MXN.
    remaining_funding_amount: float  # Last seen remaining funding amount in MXN.
    loan_number: int  # Number of loans the requisitioner has previously taken and repaid, plus one.

    def __init__(
        self,
        id: str,
        url: str,
        grade: Grade,
        interest_rate: float,
        score: int,
        destination: Destination,
        term: int,
        amount: float,
        remaining_funding_amount: float,
        loan_number: int
    ):
        self.id = id
        self.url = url
        self.grade = grade
        self.interest_rate = interest_rate
        self.score = score
        self.destination = destination
        self.term = term
        self.amount = amount
        self.remaining_funding_amount = remaining_funding_amount
        self.loan_number = loan_number

    def meets_filter(self, filter: Filter) -> bool:
        """Applies a `Filter` to a `Requisition` and returns whether the requisition meets the filter's criteria.

        Tests filter criteria one by one and stops at the first unmet criterion. Returns `True` if all filter criteria are met; returns `False` otherwise.

        Enumeration items included in both a whitelist and a blacklist are blacklisted; undefined enumeration items are ignored.

        **Warning:** this only applies base `Filter` criteria because subclass attributes are not present in this class.
        If `filter` is a `Filter` subclass, its subclass filter criteria will be ignored.
        """

        if filter.minimum_risk_grade is not None and filter.minimum_risk_grade > self.grade:
            return False
        if filter.maximum_risk_grade is not None and filter.maximum_risk_grade < self.grade:
            return False
        if filter.minimum_score is not None and filter.minimum_score > self.score:
            return False
        if filter.maximum_score is not None and filter.maximum_score < self.score:
            return False
        if filter.minimum_interest_rate is not None and filter.minimum_interest_rate > self.interest_rate:
            return False
        if filter.maximum_interest_rate is not None and filter.maximum_interest_rate < self.interest_rate:
            return False
        if filter.destination_whitelist is not None:
            isWhitelisted: bool = False
            for destination in filter.destination_whitelist:
                if destination == self.destination:
                    isWhitelisted = True
                    break
            if not isWhitelisted:
                return False
        if filter.destination_blacklist is not None:
            isBlacklisted: bool = False
            for destination in filter.destination_blacklist:
                if destination == self.destination:
                    isBlacklisted = True
                    break
            if isBlacklisted:
                return False
        if filter.minimum_term is not None and filter.minimum_term > self.term:
            return False
        if filter.maximum_term is not None and filter.maximum_term < self.term:
            return False
        if filter.minimum_amount is not None and filter.minimum_amount > self.amount:
            return False
        if filter.maximum_amount is not None and filter.maximum_amount < self.amount:
            return False
        if filter.minimum_remaining_funding_amount is not None and filter.minimum_remaining_funding_amount > self.remaining_funding_amount:
            return False
        if filter.maximum_remaining_funding_amount is not None and filter.maximum_remaining_funding_amount < self.remaining_funding_amount:
            return False
        if filter.minimum_loan_number is not None and filter.minimum_loan_number > self.loan_number:
            return False
        if filter.maximum_loan_number is not None and filter.maximum_loan_number < self.loan_number:
            return False
        return True


# TODO: keep adding members as they appear in more requisitions over time. Most I've seen at the moment are "Profesional", but there may be more for other education levels.
class Education(IntEnum):
    """Education levels enumeration, used for ordering, categorization and comparison in `DetailedRequisition`.

    Normalize collected education level strings to uppercase to create their corresponding `Education` member appropriately.

    Parse empty or undefined field as `UNKNOWN`.
    """

    UNKNOWN = 0
    TECHNICIAN = auto()  # Labeled "Técnico".
    PROFESIONAL = auto()  # Labeled "Profesional".
    MASTERS = auto()  # Labeled "Maestría".
    PHD = auto()  # Labeled "Doctorado".


# TODO: keep adding members as they appear in more requisitions over time.
class Housing(Enum):
    """Type of housing of the requisitioner. 

    Some housing options indicate similar payment compliance, or may allow subjective evaluation, hence this enumeration shouldn't be reduced to plain ordering with `IntEnum`.

    Parse empty or undefined field as `UNKNOWN`.
    """

    UNKNOWN = ""
    RENTED = "Rentada"
    LIVES_WITH_FAMILY = "Vivo con familia"
    OWNER = "Propietario"


class OccupationType(Enum):
    """Type of occupation of the requisitioner.

    Some occupation type options indicate similar payment compliance, or may allow subjective evaluation, hence this enumeration shouldn't be reduced to plain ordering with `IntEnum`.

    Parse empty or undefined field as `UNKNOWN`.
    """

    UNKNOWN = ""
    EMPLOYEE = "Empleado"
    FREELANCER = "Trabajo por mi cuenta"
    BUSINESS_OWNER = "Tengo un negocio"


class DetailedRequisition(Requisition):
    """A `DetailedRequisiton` represents a fully detailed requisition, contains all information about a requisition collected from the individual requisition page.

    Contains further information for credit analysis, including some demographics about the applicant (a.k.a. the requisitioner) as well as income and credit history details.

    Note: no personally identifiable information (PII) is collected, all requisitions are anonymized.
    """

    monthly_payment: float  # Calculated monthly payment.
    credit_history_length: int  # Credit history length in years.
    credit_history_inquiries: int
    opened_accounts: int  # Number of opened bank accounts.
    total_income: float
    total_expenses: float
    age: int
    dependents: int
    has_major_medical_insurance: bool
    has_own_vehicle: bool
    education: Education
    state_of_residence: str  # TODO: not strictly required for evaluation, an Enum could be created for this. State of residence in Mexico.
    housing: Housing
    occupation: str  # Occupation as indicated by the requisitioner. TODO: this is an open value indicating the requisitioners job position. Empty string may be parsed as having an elevated risk of defaulting, unless type of employment indicates otherwise (like being a business owner or freelancer).
    tenure: int  # Number of years at the last reported occupation, as indicated by the requisitioner.
    occupation_type: OccupationType

    def __init__(
        self, 
        base_requisition: Requisition,
        monthly_payment: float,
        credit_history_length: int,
        credit_history_inquiries: int,
        opened_accounts: int,
        total_income: float,
        total_expenses: float,
        age: int,
        dependents: int,
        has_major_medical_insurance: bool,
        has_own_vehicle: bool,
        education: Education,
        state_of_residence: str,
        housing: Housing,
        occupation: str,
        tenure: int,
        occupation_type: OccupationType
    ):
        super().__init__(**base_requisition.__dict__)  # Passed as `dict` so it can be unpacked.
        self.monthly_payment = monthly_payment
        self.credit_history_length = credit_history_length
        self.credit_history_inquiries = credit_history_inquiries
        self.opened_accounts = opened_accounts
        self.total_income = total_income
        self.total_expenses = total_expenses
        self.age = age
        self.dependents = dependents
        self.has_major_medical_insurance = has_major_medical_insurance
        self.has_own_vehicle = has_own_vehicle
        self.education = education
        self.state_of_residence = state_of_residence
        self.housing = housing
        self.occupation = occupation
        self.tenure = tenure
        self.occupation_type = occupation_type

    def meets_filter(self, filter: Filter | DetailedFilter) -> bool:
        """Applies a `Filter` or `DetailedFilter` to a `DetailedRequisition` and returns whether the requisition meets the filter's criteria.

        Tests filter criteria one by one and stops at the first unmet criterion. Returns `True` if all filter criteria are met; returns `False` otherwise.

        Enumeration items included in both a whitelist and a blacklist are blacklisted; undefined enumeration items are ignored.

        This overriding method applies all `DetailedFilter` criteria when `filter` is a `DetailedFilter`,
        otherwise it applies only base `Filter` criteria.
        """

        # Evaluate only base `Filter` criteria if the filter is not a `DetailedFilter` to avoid exceptions caused by accessing missing attributes.
        if not isinstance(filter, DetailedFilter):
            return super().meets_filter(filter)
        # Evaluate all `DetailedFilter` criteria.
        if not super().meets_filter(filter):
            return False
        if filter.minimum_monthly_payment is not None and filter.minimum_monthly_payment > self.monthly_payment:
            return False
        if filter.maximum_monthly_payment is not None and filter.maximum_monthly_payment < self.monthly_payment:
            return False
        if filter.minimum_credit_history_length is not None and filter.minimum_credit_history_length > self.credit_history_length:
            return False
        if filter.maximum_credit_history_length is not None and filter.maximum_credit_history_length < self.credit_history_length:
            return False
        if filter.minimum_credit_history_inquiries is not None and filter.minimum_credit_history_inquiries > self.credit_history_inquiries:
            return False
        if filter.maximum_credit_history_inquiries is not None and filter.maximum_credit_history_inquiries < self.credit_history_inquiries:
            return False
        if filter.minimum_opened_accounts is not None and filter.minimum_opened_accounts > self.opened_accounts:
            return False
        if filter.maximum_opened_accounts is not None and filter.maximum_opened_accounts < self.opened_accounts:
            return False
        if filter.minimum_total_income is not None and filter.minimum_total_income > self.total_income:
            return False
        if filter.maximum_total_income is not None and filter.maximum_total_income < self.total_income:
            return False
        if filter.minimum_total_expenses is not None and filter.minimum_total_expenses > self.total_expenses:
            return False
        if filter.maximum_total_expenses is not None and filter.maximum_total_expenses < self.total_expenses:
            return False
        if filter.minimum_age is not None and filter.minimum_age > self.age:
            return False
        if filter.maximum_age is not None and filter.maximum_age < self.age:
            return False
        if filter.minimum_dependents is not None and filter.minimum_dependents > self.dependents:
            return False
        if filter.maximum_dependents is not None and filter.maximum_dependents < self.dependents:
            return False
        if filter.has_major_medical_insurance is not None and filter.has_major_medical_insurance != self.has_major_medical_insurance:
            return False
        if filter.has_own_vehicle is not None and filter.has_own_vehicle != self.has_own_vehicle:
            return False
        if filter.housing_whitelist is not None:
            isWhitelisted: bool = False
            for housing in filter.housing_whitelist:
                if housing == self.housing:
                    isWhitelisted = True
                    break
            if not isWhitelisted:
                return False
        if filter.housing_blacklist is not None:
            isBlacklisted: bool = False
            for housing in filter.housing_blacklist:
                if housing == self.housing:
                    isBlacklisted = True
                    break
            if isBlacklisted:
                return False
        if filter.minimum_tenure is not None and filter.minimum_tenure > self.tenure:
            return False
        if filter.maximum_tenure is not None and filter.maximum_tenure < self.tenure:
            return False
        if filter.occupation_type_whitelist is not None:
            isWhitelisted: bool = False
            for occupation_type in filter.occupation_type_whitelist:
                if occupation_type == self.occupation_type:
                    isWhitelisted = True
                    break
            if not isWhitelisted:
                return False
        if filter.occupation_type_blacklist is not None:
            isBlacklisted: bool = False
            for occupation_type in filter.occupation_type_blacklist:
                if occupation_type == self.occupation_type:
                    isBlacklisted = True
                    break
            if isBlacklisted:
                return False
        return True


class Filter():
    """A `Filter` represents a set of filter criteria for a `Requisition`.

    Can be used to filter a list of `Requisition` objects based on the filter criteria.

    It is not mandatory to create a `Filter` with every filter criteria, 
    omitted filter criteria will be ignored when applying the filter to a `Requisition`.
    Likewise, filter criteria not included in filters in the YAML file will be ignored.

    Adding multiple filters to a YAML file and applying them to a list of requisitions results in the union of their results;
    items matching any of the filters will be included in the filtered list.
    """

    minimum_risk_grade: Grade | None
    maximum_risk_grade: Grade | None
    minimum_score: int | None
    maximum_score: int | None
    minimum_interest_rate: float | None
    maximum_interest_rate: float | None
    destination_whitelist: list[Destination] | None
    destination_blacklist: list[Destination] | None
    minimum_term: int | None
    maximum_term: int | None
    minimum_amount: float | None
    maximum_amount: float | None
    minimum_remaining_funding_amount: float | None
    maximum_remaining_funding_amount: float | None
    minimum_loan_number: int | None
    maximum_loan_number: int | None

    def __init__(
        self,
        minimum_risk_grade: Grade | None = None,
        maximum_risk_grade: Grade | None = None,
        minimum_score: int | None = None,
        maximum_score: int | None = None,
        minimum_interest_rate: float | None = None,
        maximum_interest_rate: float | None = None,
        destination_whitelist: list[Destination] | None = None,
        destination_blacklist: list[Destination] | None = None,
        minimum_term: int | None = None,
        maximum_term: int | None = None,
        minimum_amount: float | None = None,
        maximum_amount: float | None = None,
        minimum_remaining_funding_amount: float | None = None,
        maximum_remaining_funding_amount: float | None = None,
        minimum_loan_number: int | None = None,
        maximum_loan_number: int | None = None
    ):
        self.minimum_risk_grade = minimum_risk_grade
        self.maximum_risk_grade = maximum_risk_grade
        self.minimum_score = minimum_score
        self.maximum_score = maximum_score
        self.minimum_interest_rate = minimum_interest_rate
        self.maximum_interest_rate = maximum_interest_rate
        self.destination_whitelist = destination_whitelist
        self.destination_blacklist = destination_blacklist
        self.minimum_term = minimum_term
        self.maximum_term = maximum_term
        self.minimum_amount = minimum_amount
        self.maximum_amount = maximum_amount
        self.minimum_remaining_funding_amount = minimum_remaining_funding_amount
        self.maximum_remaining_funding_amount = maximum_remaining_funding_amount
        self.minimum_loan_number = minimum_loan_number
        self.maximum_loan_number = maximum_loan_number

    @classmethod
    def parse_all_from_yaml(cls, path: str) -> list[Self]:
        """Creates a list of `Filter` objects from a YAML file.

        Parses a YAML file and creates a list of `Filter` objects, from the first YAML document in the file.

        Note that this will ignore detailed filter criteria in the YAML file; to parse all filter criteria, use the corresponding method from `DetailedFilter`.

        Returns a list of `Filter` objects contained in the YAML file.

        Raises an exception if the YAML file cannot be parsed for any reason.
        """

        data: Any
        filters: list[Self] = []
        # Gets __init__ method parameters of the class. This is a dict-like object, and it contains the "self" parameter.
        # Note that these contain the "self" argument, which is not a valid keyword argument for the constructor.
        filter_parameters = inspect.signature(cls.__init__).parameters
        with open(file=path, mode="r", encoding="utf-8") as yaml_file:
            # "safe_load" is restricted to parsing YAML objects as native Python data types, so here they are parsed as dictionaries.
            # "load" can instantiate custom classes right away, but opens the risk of malicious code injection from untrusted YAML files.
            data = safe_load(yaml_file)
        for filter in data["filters"]:
            # Whitelists and blacklists must be processed to convert values to Enum instances to make them compatible with the __init__ constructor. Uses list comprehension.
            processed_filter: Any = filter.copy()  # Creates a working copy because the filter iterator is read-only.
            if "destination_whitelist" in processed_filter and processed_filter["destination_whitelist"] is not None:
                processed_filter["destination_whitelist"] = [
                    Destination(destination_value) for destination_value in processed_filter["destination_whitelist"]
                ]
            if "destination_blacklist" in processed_filter and processed_filter["destination_blacklist"] is not None:
                processed_filter["destination_blacklist"] = [
                    Destination(destination_value) for destination_value in processed_filter["destination_blacklist"]
                ]
            # Filters out invalid or undefined keyword arguments from the aggregate data.
            # This is because the "**" unpack operator passes all key-value pairs as keyword arguments to the __init__ constructor,
            # including invalid or undefined keyword arguments, and passing them to the constructor raises an Exception.
            for key, _ in processed_filter.items():
                if key not in filter_parameters.keys() or key == "self":  # The "self" argument is not a valid keyword argument for the constructor.
                    processed_filter.pop(key)
            filters.append(cls(**processed_filter))
        return filters

# TODO: additional calculated filters such as "income-expense ratio", "remaining funding amount ratio to amount ratio" and "monthly payment to free income ratio" could be added to this.
class DetailedFilter(Filter):
    """A `DetailedFilter` represents a full set of detailed filter criteria for a `Requisition`.
    
    Can be used to filter a list of `DetailedRequisition` objects based on the filter criteria.
    """

    minimum_monthly_payment: float | None
    maximum_monthly_payment: float | None
    minimum_credit_history_length: int | None
    maximum_credit_history_length: int | None
    minimum_credit_history_inquiries: int | None
    maximum_credit_history_inquiries: int | None
    minimum_opened_accounts: int | None
    maximum_opened_accounts: int | None
    minimum_total_income: float | None
    maximum_total_income: float | None
    minimum_total_expenses: float | None
    maximum_total_expenses: float | None
    minimum_age: int | None
    maximum_age: int | None
    minimum_dependents: int | None
    maximum_dependents: int | None
    has_major_medical_insurance: bool | None
    has_own_vehicle: bool | None
    # TODO: or replace with white/black lists? To avoid having to check inconsistent/inverted enum thresholds.
    # minimum_education: Education
    # maximum_education: Education
    # TODO: replace open string argument with enum in requisitions.py, and reference it here.
    # state_of_residence_whitelist: list[str]
    # state_of_residence_blacklist: list[str]
    housing_whitelist: list[Housing] | None
    housing_blacklist: list[Housing] | None
    # occupation  # TODO: is this even filterable? It is an open string. Only if the user wanted to check whether it is empty or not. Or have it analyzed some other way.
    minimum_tenure: int | None
    maximum_tenure: int | None
    occupation_type_whitelist: list[OccupationType]
    occupation_type_blacklist: list[OccupationType]

    def __init__(
        self,
        base_filter: Filter,
        minimum_monthly_payment: float | None = None,
        maximum_monthly_payment: float | None = None,
        minimum_credit_history_length: int | None = None,
        maximum_credit_history_length: int | None = None,
        minimum_credit_history_inquiries: int | None = None,
        maximum_credit_history_inquiries: int | None = None,
        minimum_opened_accounts: int | None = None,
        maximum_opened_accounts: int | None = None,
        minimum_total_income: float | None = None,
        maximum_total_income: float | None = None,
        minimum_total_expenses: float | None = None,
        maximum_total_expenses: float | None = None,
        minimum_age: int | None = None,
        maximum_age: int | None = None,
        minimum_dependents: int | None = None,
        maximum_dependents: int | None = None,
        has_major_medical_insurance: bool | None = None,
        has_own_vehicle: bool | None = None,
        housing_whitelist: list[Housing] | None = None,
        housing_blacklist: list[Housing] | None = None,
        minimum_tenure: int | None = None,
        maximum_tenure: int | None = None,
        occupation_type_whitelist: list[OccupationType] | None = None,
        occupation_type_blacklist: list[OccupationType] | None = None
    ):
        super().__init__(**base_filter.__dict__)  # Passed as `dict` so it can be unpacked.
        self.minimum_monthly_payment = minimum_monthly_payment
        self.maximum_monthly_payment = maximum_monthly_payment
        self.minimum_credit_history_length = minimum_credit_history_length
        self.maximum_credit_history_length = maximum_credit_history_length
        self.minimum_credit_history_inquiries = minimum_credit_history_inquiries
        self.maximum_credit_history_inquiries = maximum_credit_history_inquiries
        self.minimum_opened_accounts = minimum_opened_accounts
        self.maximum_opened_accounts = maximum_opened_accounts
        self.minimum_total_income = minimum_total_income
        self.maximum_total_income = maximum_total_income
        self.minimum_total_expenses = minimum_total_expenses
        self.maximum_total_expenses = maximum_total_expenses
        self.minimum_age = minimum_age
        self.maximum_age = maximum_age
        self.minimum_dependents = minimum_dependents
        self.maximum_dependents = maximum_dependents
        self.has_major_medical_insurance = has_major_medical_insurance
        self.has_own_vehicle = has_own_vehicle
        self.housing_whitelist = housing_whitelist
        self.housing_blacklist = housing_blacklist
        self.minimum_tenure = minimum_tenure
        self.maximum_tenure = maximum_tenure
        self.occupation_type_whitelist = occupation_type_whitelist
        self.occupation_type_blacklist = occupation_type_blacklist

    @classmethod
    def parse_all_from_yaml(cls, path: str) -> list[Self]:
        """Creates a list of `DetailedFilter` objects from a YAML file.

        Parses a YAML file and creates a list of `DetailedFilter` objects, from the first YAML document in the file.

        Returns a list of `DetailedFilter` objects contained in the YAML file.

        Raises an exception if the YAML file cannot be parsed for any reason.
        """

        data: Any
        detailed_filters: list[Self] = []
        # Gets __init__ method parameters of each class. These are dict-like objects, and they contain the "self" parameter.
        base_filter_parameters = inspect.signature(Filter.__init__).parameters
        detailed_filter_parameters = inspect.signature(cls.__init__).parameters
        with open(file=path, mode="r", encoding="utf-8") as yaml_file:
            data = safe_load(yaml_file)  # Gets all filters, with every filter criteria from both base and detailed filter classes.
        for full_filter in data["filters"]:
            # Classifies arguments of each class from the aggregate data.
            base_filter_arguments: dict[str, Any] = {}
            detailed_filter_arguments: dict[str, Any] = {}
            base_filter: Filter  # Required argument for the DetailedFilter constructor.
            detailed_filter: Self
            for key, value in full_filter.items():
                # Expects no shadowed attributes between these classes. Also, the "self" argument is not a valid keyword argument for the constructor.
                if key in base_filter_parameters.keys() and key != "self":
                    base_filter_arguments[key] = value
                if key in detailed_filter_parameters.keys() and key != "self":
                    detailed_filter_arguments[key] = value
            # Whitelists and blacklists must be processed to convert values to Enum instances to make them compatible with __init__ constructors. Uses list comprehension.
            # Parses base Filter enums first, in order to create the base Filter argument required for the DetailedFilter constructor.
            if "destination_whitelist" in base_filter_arguments and base_filter_arguments.destination_whitelist is not None:
                base_filter_arguments.destination_whitelist = [
                    Destination(destination_value) for destination_value in base_filter_arguments.destination_whitelist
                ]
            if "destination_blacklist" in base_filter_arguments and base_filter_arguments.destination_blacklist is not None:
                base_filter_arguments.destination_blacklist = [
                    Destination(destination_value) for destination_value in base_filter_arguments.destination_blacklist
                ]
            base_filter = Filter(**base_filter_arguments)
            if "housing_whitelist" in detailed_filter_arguments and detailed_filter_arguments.housing_whitelist is not None:
                detailed_filter_arguments.housing_whitelist = [
                    Housing(housing_value) for housing_value in detailed_filter_arguments.housing_whitelist
                ]
            if "housing_blacklist" in detailed_filter_arguments and detailed_filter_arguments.housing_blacklist is not None:
                detailed_filter_arguments.housing_blacklist = [
                    Housing(housing_value) for housing_value in detailed_filter_arguments.housing_blacklist
                ]
            if "occupation_type_whitelist" in detailed_filter_arguments and detailed_filter_arguments.occupation_type_whitelist is not None:
                detailed_filter_arguments.occupation_type_whitelist = [
                    OccupationType(occupation_type_value) for occupation_type_value in detailed_filter_arguments.occupation_type_whitelist
                ]
            if "occupation_type_blacklist" in detailed_filter_arguments and detailed_filter_arguments.occupation_type_blacklist is not None:
                detailed_filter_arguments.occupation_type_blacklist = [
                    OccupationType(occupation_type_value) for occupation_type_value in detailed_filter_arguments.occupation_type_blacklist
                ]
            detailed_filter = cls(base_filter=base_filter, **detailed_filter_arguments)
            detailed_filters.append(detailed_filter)
        return detailed_filters


if __name__ == "__main__":
    pass