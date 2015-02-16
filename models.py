from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.types import DateTime

Base = declarative_base()

class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True)
    name = Column(String)

class MachineType(Base):
    __tablename__ = "machinetypes"

    id = Column(Integer, primary_key=True)
    name = Column(String)

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True)
    tufts_id = Column(Integer)
    room = Column(Integer, ForeignKey("buildings.id"))
    type = Column(Integer, ForeignKey("machinetypes.id"))


class UsageRecord(Base):
    __tablename__ = "usagerecords"

    id = Column(Integer, primary_key=True)
    machine = Column(Integer, ForeignKey("machines.id"))
    available = Column(Integer)
    time_remaining = Column(Integer)
    timestamp = Column(DateTime)