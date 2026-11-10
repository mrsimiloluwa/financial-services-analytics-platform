"""Deterministic generator for commercial, SME, and institutional customer profiles."""

import random
from datetime import date, timedelta

from data_platform.generator.schemas import CustomerRecord


class CustomerEngine:
    """Generates synthetic customer entities across banking segments."""

    SEGMENTS: list[str] = ["RETAIL_WEALTH", "COMMERCIAL_SME", "INSTITUTIONAL"]
    SEGMENT_WEIGHTS: list[float] = [0.50, 0.35, 0.15]

    LEGAL_ENTITIES: list[str] = ["ENTITY_EU_CENTRAL", "ENTITY_UK_LTD", "ENTITY_US_CORP"]
    LEGAL_ENTITY_WEIGHTS: list[float] = [0.60, 0.25, 0.15]

    FIRST_NAMES: list[str] = [
        "Alexander",
        "Beatrice",
        "Carlos",
        "Diana",
        "Emil",
        "Fatima",
        "Giovanni",
        "Helena",
        "Ibrahim",
        "Juliana",
        "Klaus",
        "Lucia",
        "Marcus",
        "Nadia",
        "Oliver",
    ]
    LAST_NAMES: list[str] = [
        "Müller",
        "Dubois",
        "Rossi",
        "Schmidt",
        "Lefebvre",
        "Van Dijk",
        "Moretti",
        "Novak",
        "Andersson",
        "Kowalski",
        "Schneider",
        "Fischer",
        "Weber",
        "Alvarez",
    ]
    CORP_PREFIXES: list[str] = [
        "Apex",
        "Beacon",
        "Crestview",
        "Dynamic",
        "Equinox",
        "Frontier",
        "Global",
        "Horizon",
        "Imperial",
        "Jupiter",
        "Kestrel",
        "Luminary",
        "Meridian",
        "Nexus",
        "Olympus",
        "Pinnacle",
        "Quantum",
        "Radiant",
        "Summit",
        "Titan",
        "Vanguard",
    ]
    CORP_SUFFIXES: list[str] = [
        "Treasury AG",
        "Holdings B.V.",
        "Logistics GmbH",
        "Capital S.A.",
        "Technologies S.r.l.",
        "Trading Corp",
        "Services Ltd",
        "Solutions OY",
        "Commercial Sp. z o.o.",
    ]

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_customers(
        self,
        count: int = 50,
        start_date: date = date(2025, 1, 1),
        end_date: date = date(2025, 12, 31),
    ) -> list[CustomerRecord]:
        """Generate a deterministic list of customer records validated by Pydantic."""
        customers: list[CustomerRecord] = []
        total_days = max(1, (end_date - start_date).days)

        for i in range(1, count + 1):
            customer_id = f"CUST_{i:04d}"
            segment = self.rng.choices(self.SEGMENTS, weights=self.SEGMENT_WEIGHTS, k=1)[0]
            legal_entity = self.rng.choices(
                self.LEGAL_ENTITIES,
                weights=self.LEGAL_ENTITY_WEIGHTS,
                k=1,
            )[0]

            if segment == "RETAIL_WEALTH":
                first = self.rng.choice(self.FIRST_NAMES)
                last = self.rng.choice(self.LAST_NAMES)
                customer_name = f"{first} {last}"
            else:
                prefix = self.rng.choice(self.CORP_PREFIXES)
                suffix = self.rng.choice(self.CORP_SUFFIXES)
                customer_name = f"{prefix} {suffix}"

            # 90% Active, 7% Suspended, 3% Closed
            status = self.rng.choices(
                ["ACTIVE", "SUSPENDED", "CLOSED"], weights=[0.90, 0.07, 0.03], k=1
            )[0]
            onboarding_offset = self.rng.randint(0, total_days)
            onboarding_date = start_date + timedelta(days=onboarding_offset)

            record = CustomerRecord(
                customer_id=customer_id,
                legal_entity_id=legal_entity,
                customer_name=customer_name,
                customer_segment=segment,
                status=status,
                onboarding_date=onboarding_date,
            )
            customers.append(record)

        return customers
