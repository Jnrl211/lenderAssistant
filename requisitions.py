from enum import Enum, IntEnum, auto


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


class Requisition():
    """A `Requisition` contains basic information about a requisition, collected from the requisition list page."""

    id: str
    url: str
    grade: Grade
    interest_rate: float  # Stored as percentage value (not decimal form).
    score: int
    destination: str
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
        destination: str,
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


# TODO: keep adding members as they appear in more requisitions over time. Most I've seen at the moment are "Profesional", but there may be more for other education levels.
class Education(IntEnum):
    """Education levels enumeration, used for ordering, categorization and comparison in `DetailedRequisition`.
    
    Normalize collected education level strings to uppercase to create their corresponding `Education` member appropriately.
    
    Parse empty or undefined field as `UNKNOWN`.
    """

    UNKNOWN = ""
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
    state_of_residence: str = ""  # TODO: not strictly required for evaluation, an Enum could be created for this. State of residence in Mexico.
    housing: Housing
    # TODO: this is often a custom value indicating the requisitioners job position. Empty string may be parsed as having an elevated risk of defaulting, 
    #       unless type of employment indicates otherwise (like being a business owner or freelancer). Occupation as indicated by the requisitioner.
    occupation: str  
    tenure: int  # Number of years at the last reported occupation, as indicated by the requisitioner.
    occupation_type: OccupationType

    def __init__(
        self, 
        baseRequisition: Requisition,
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
        super().__init__(
            baseRequisition.id,
            baseRequisition.url,
            baseRequisition.grade,
            baseRequisition.interest_rate,
            baseRequisition.score,
            baseRequisition.destination,
            baseRequisition.term,
            baseRequisition.amount,
            baseRequisition.remaining_funding_amount,
            baseRequisition.loan_number
        )
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


if __name__ == "__main__":
    pass