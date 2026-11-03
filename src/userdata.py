from dataclasses import dataclass


@dataclass
class CallerData:
    name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None

    # Existing patients who match the demo records
    verified: bool = False

    # New patients who may proceed with booking only
    new_patient: bool = False

    # Buffers for speech that may arrive in multiple fragments
    phone_input_buffer: str = ""
    dob_input_buffer: str = ""

    # Tracks which identity step is currently required
    identity_stage: str = "name"