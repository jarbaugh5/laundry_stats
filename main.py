# noinspection PyPackageRequirements
"""
The goal here is to get and store data about the
laundry machine usage here at tufts
"""

import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import *

# Start Constants
BASE_URL = "http://www.laundryview.com/"
STATIC_ROOM_EXT = "staticRoomData.php?location="
DYN_ROOM_EXT = "/dynamicRoomData.php?location="

POLL_INTERVAL = 30  # In seconds
# End Constants


def get_static_data_link(location_id):
    return BASE_URL + STATIC_ROOM_EXT + str(location_id)


def get_dyn_data_link(location_id):
    return BASE_URL + DYN_ROOM_EXT + str(location_id)


def get_room_ids():
    ids = []
    r = requests.get(BASE_URL)
    soup = BeautifulSoup(r.text)
    for link in soup.find_all("a", "a-room"):
        parse_result = urlparse(link["href"])
        parse_query = parse_qs(parse_result.query)
        ids.append(parse_query["lr"][0])
    return ids


def get_static_room_info(id):
    r = requests.get(get_static_data_link(id))
    query = parse_qs(r.text)
    room = dict()
    room["id"] = id
    room["name"] = query["name"][0].replace(':\n', '')
    num_machines = 0
    for key in query.keys():
        if "machineData" in key:
            num_machines += 1
            room[key] = dict()
            room[key]["id"] = query[key][0].split(":")[5]
            room[key]["type"] = ""
            if "dry" in query[key][0]:
                room[key]["type"] = "dry"
            elif "wash" in query[key][0]:
                room[key]["type"] = "wash"
            elif "dblDry" in query[key][0]:
                room[key]["type"] = "dblDry"
                room[key]["id2"] = query[key][0].split(":")[9]
            else:
                num_machines -= 1
                del room[key]
    room["num_machines"] = num_machines
    return room


def load_dyn_room_data(session, room):
    timestamp = datetime.now()
    r = requests.get(get_dyn_data_link(room["id"]))
    query = parse_qs(r.text)
    for i in range(0, room["num_machines"]):
        machine_static_name = "machineData" + str(i + 1)
        machine_name = "machineStatus" + str(i + 1)
        machine_data = room[machine_static_name]
        machine = query[machine_name]
        if machine_data["type"] == "dblDry":
            data1 = machine[0].split(":")[0:9]
            data2 = machine[0].split(":")[9:]
            id1 = machine_data["id"]
            id2 = machine_data["id2"]
            available1 = int(data1[0])
            available2 = int(data2[0].replace('\n', ''))
            time_remaining1 = 0
            time_remaining2 = 0
            if not available1:
                time_remaining1 = data1[1]
            if not available2:
                time_remaining2 = data2[1]
            add_record(session, id1, available1, time_remaining1, timestamp)
            add_record(session, id2, available2, time_remaining2, timestamp)

        else:
            machine_static_name = "machineData" + str(i + 1)
            machine_name = "machineStatus" + str(i + 1)
            machine_data = room[machine_static_name]
            machine = query[machine_name]

            id = machine_data["id"]
            data = machine[0].split(":")
            available = data[0]
            time_remaining = 0
            if not available:
                time_remaining = data[1]
            add_record(session, id, available, time_remaining, timestamp)


def build_room_list():
    rooms = []
    for room_id in get_room_ids():
        rooms.append(get_static_room_info(room_id))
    return rooms


def add_record(session, machine_id, available, time_remaining, timestamp):
    machine = session.query(Machine).filter_by(tufts_id=machine_id).one()
    record = UsageRecord(machine=machine.id, available=int(available),
                         time_remaining=int(time_remaining), timestamp=timestamp)
    session.add(record)
    session.commit()
    # print("[{0}] {1}: {2}, {3}".format(timestamp, machine_id, available, time_remaining))


def poll_rooms(session, rooms):
    delta = timedelta(seconds=POLL_INTERVAL)
    while True:
        start_time = datetime.now()
        for room in rooms:
            load_dyn_room_data(session, room)
            time_diff = start_time + delta - datetime.now()
        print("[{0}] Loaded data in {1} seconds".format(str(datetime.now()),
                                                        (datetime.now() - start_time).total_seconds()))
        if time_diff.total_seconds() > 0:
            time.sleep(time_diff.total_seconds())


def ensure_schema(rooms, session):
    for room in rooms:
        if session.query(Building).filter_by(name=room["name"]).count() == 0:
            building = Building(name=room["name"])
            session.add(building)
            session.commit()
        building = session.query(Building).filter_by(name=room["name"]).one()

        for i in range(0, room["num_machines"]):
            machine_static_name = "machineData" + str(i + 1)
            machine_data = room[machine_static_name]
            type_name = machine_data["type"]

            if session.query(MachineType).filter_by(name=type_name).count() == 0:
                machine_type = MachineType(name=type_name)
                session.add(machine_type)
                session.commit()
            machine_type = session.query(MachineType).filter_by(name=type_name).one()

            if session.query(Machine).filter_by(tufts_id=machine_data["id"]).count() == 0:
                machine = Machine(tufts_id=int(machine_data["id"]), room=building.id, type=machine_type.id)
                session.add(machine)
                session.commit()

            if "id2" in machine_data and session.query(Machine).filter_by(tufts_id=machine_data["id2"]).count() == 0:
                machine = Machine(tufts_id=int(machine_data["id2"]), room=building.id, type=machine_type.id)
                session.add(machine)
                session.commit()


def main():
    engine = create_engine('sqlite:///:memory', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    room_list = build_room_list()
    ensure_schema(room_list, session)
    poll_rooms(session, room_list)


if __name__ == "__main__":
    main()