from datetime import datetime
from decimal import Decimal
from typing import TypeAlias

InstrumentId: TypeAlias = str
SymbolToken: TypeAlias = str
ISIN: TypeAlias = str
BloomInstrumentId: TypeAlias = str

Price: TypeAlias = Decimal
Quantity: TypeAlias = int
Volume: TypeAlias = int

Timestamp: TypeAlias = datetime
Fraction: TypeAlias = Decimal
