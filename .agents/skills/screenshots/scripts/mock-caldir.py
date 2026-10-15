"""Write a mock caldir with realistic events for marketing screenshots.

Usage: mock-caldir.py <calendar_dir> [YYYY-MM-DD]

Events are laid out around the week containing the given date (default:
today), in the system timezone. The directory is wiped and rewritten.
"""
import re
import shutil
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(sys.argv[1])
anchor = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
MON = anchor - timedelta(days=anchor.weekday())


def system_tz():
    try:
        return str(Path("/etc/localtime").resolve()).split("zoneinfo/", 1)[1]
    except (IndexError, OSError):
        return "UTC"


TZID = system_tz()

CALENDARS = {
    "work": ("Work", "#4f8ef7"),
    "personal": ("Personal", "#f59e0b"),
    "fitness": ("Fitness", "#22c55e"),
    "family": ("Family", "#ec4899"),
    "holidays": ("Holidays", "#a78bfa"),
}

PEOPLE = {
    "maya": ("Maya Chen", "maya@northwind.io"),
    "jordan": ("Jordan Ellis", "jordan@northwind.io"),
    "priya": ("Priya Shah", "priya@northwind.io"),
    "sam": ("Sam Okafor", "sam@northwind.io"),
    "lea": ("Léa Martin", "lea@northwind.io"),
    "alex": ("Alex Rivera", "alex.rivera@fastmail.com"),
}
ME = ("Tristan", "tristan@northwind.io")
STATUSES = ["ACCEPTED", "ACCEPTED", "TENTATIVE", "ACCEPTED", "NEEDS-ACTION"]

events = []


def d(week, dow):
    """Day `dow` (0 = Monday) of the week `week` weeks from the anchor week."""
    return MON + timedelta(weeks=week, days=dow)


def ev(cal, title, day, start=None, end=None, *, end_day=None, location=None,
       desc=None, rrule=None, people=(), meet=False, organizer=True):
    """Queue an event; omit start/end for an all-day event."""
    events.append(dict(cal=cal, title=title, day=day, start=start, end=end,
                       end_day=end_day, location=location, desc=desc, rrule=rrule,
                       people=people, meet=meet, organizer=organizer))


def esc(s):
    return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def fold(line):
    out, b = [], line.encode()
    while len(b) > 74:
        cut = 74
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode())
        b = b" " + b[cut:]
    out.append(b.decode())
    return "\r\n".join(out)


def local(day, hm):
    return f"{day:%Y%m%d}T{hm.replace(':', '')}00"


def to_ics(e):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:CALDIR", "BEGIN:VEVENT",
             f"UID:{uuid.uuid4()}@caldir", "DTSTAMP:20260101T090000Z"]
    if e["start"]:
        # Local wall-clock times, so recurrences keep their hour across DST.
        lines.append(f"DTSTART;TZID={TZID}:{local(e['day'], e['start'])}")
        lines.append(f"DTEND;TZID={TZID}:{local(e['end_day'] or e['day'], e['end'])}")
    else:
        last = e["end_day"] or e["day"]
        lines.append(f"DTSTART;VALUE=DATE:{e['day']:%Y%m%d}")
        lines.append(f"DTEND;VALUE=DATE:{last + timedelta(days=1):%Y%m%d}")
    lines.append(f"SUMMARY:{esc(e['title'])}")
    if e["location"]:
        lines.append(f"LOCATION:{esc(e['location'])}")
    if e["desc"]:
        lines.append(f"DESCRIPTION:{esc(e['desc'])}")
    if e["rrule"]:
        lines.append(f"RRULE:{e['rrule']}")
    if e["people"]:
        org = ME if e["organizer"] else PEOPLE[e["people"][0]]
        lines.append(f"ORGANIZER;CN={org[0]}:mailto:{org[1]}")
        lines.append(f"ATTENDEE;CN={ME[0]};PARTSTAT=ACCEPTED:mailto:{ME[1]}")
        for i, p in enumerate(e["people"]):
            name, mail = PEOPLE[p]
            lines.append(f"ATTENDEE;CN={name};PARTSTAT={STATUSES[i % len(STATUSES)]}:mailto:{mail}")
    if e["meet"]:
        code = uuid.uuid4().hex
        lines.append(f"X-GOOGLE-CONFERENCE:https://meet.google.com/{code[:3]}-{code[3:7]}-{code[7:10]}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:40]


# --- Recurring ---------------------------------------------------------------
START = d(-3, 0)
TEAM = ("maya", "jordan", "priya", "sam", "lea")
ev("work", "Daily standup", START, "09:30", "09:45",
   rrule="FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", people=TEAM[:4], meet=True,
   desc="Yesterday / today / blockers. Keep it under 15 minutes.")
ev("fitness", "Gym", START, "07:00", "08:00", rrule="FREQ=WEEKLY;BYDAY=MO,WE,FR",
   location="PureGym Shoreditch")
ev("fitness", "Yoga", d(-3, 3), "18:30", "19:30", rrule="FREQ=WEEKLY;BYDAY=TH",
   location="Triyoga Soho")
ev("fitness", "Long run", d(-3, 5), "09:00", "10:30", rrule="FREQ=WEEKLY;BYDAY=SA",
   location="Victoria Park", desc="Easy pace, 12 km")
ev("work", "1:1 with Maya", d(-3, 1), "14:00", "14:30", rrule="FREQ=WEEKLY;BYDAY=TU",
   people=("maya",), meet=True, organizer=False)
ev("work", "Sprint planning", START, "10:00", "11:30", rrule="FREQ=WEEKLY;INTERVAL=2;BYDAY=MO",
   people=TEAM, location="Room 4.02", meet=True)
ev("work", "Sprint retro", d(-3, 4), "16:00", "17:00",
   rrule="FREQ=WEEKLY;INTERVAL=2;BYDAY=FR", people=TEAM, meet=True)
ev("family", "Call grandma", d(-3, 6), "16:00", "16:30", rrule="FREQ=WEEKLY;BYDAY=SU")

# --- Anchor week --------------------------------------------------------------
ev("work", "Design review: onboarding", d(0, 0), "13:00", "14:00",
   people=("lea", "maya", "priya"), meet=True, location="Room 3.10",
   desc="Walk through the new onboarding flow.\nFigma: figma.com/file/onboarding-v3")
ev("personal", "Dinner with Sam & Priya", d(0, 0), "19:30", "21:30", location="Dishoom, Shoreditch")
ev("work", "Product sync", d(0, 1), "11:00", "12:00", people=("jordan", "lea"), meet=True)
ev("work", "Focus time", d(0, 1), "15:00", "17:30", desc="No meetings. Finish the sync engine PR.")
ev("personal", "Lunch with Alex", d(0, 2), "12:30", "13:30", location="Padella, Borough Market",
   people=("alex",))
ev("work", "Customer call: Northwind", d(0, 2), "15:00", "15:45",
   people=("sam", "jordan"), meet=True,
   desc="Agenda:\n• Q4 roadmap\n• Calendar sharing feedback")
ev("personal", "Pottery class", d(0, 2), "19:00", "21:00", location="Turning Earth, Hoxton")
ev("work", "Quarterly planning", d(0, 3), "10:00", "12:30", location="Room 4.02", people=TEAM)
ev("work", "Interview: Senior Frontend", d(0, 3), "14:00", "15:00", people=("priya",), meet=True)
ev("personal", "Coffee with Jordan", d(0, 3), "16:00", "16:30", location="Prufrock Coffee")
ev("work", "v2.4 release", d(0, 4))
ev("work", "Team lunch", d(0, 4), "12:00", "13:30", location="Flat Iron, Covent Garden")
ev("personal", "Drinks at The Albion", d(0, 4), "18:30", "20:30")
ev("personal", "Farmers market", d(0, 5), "11:30", "12:30", location="Broadway Market")
ev("family", "Mum's birthday", d(0, 5), rrule="FREQ=YEARLY")
ev("family", "Birthday dinner for Mum", d(0, 5), "18:30", "21:30", location="The River Café")
ev("personal", "Meal prep", d(0, 6), "17:30", "18:30")

# --- Surrounding weeks --------------------------------------------------------
ev("work", "Design offsite", d(-2, 2), end_day=d(-2, 3))
ev("work", "Q4 kickoff", d(-2, 0), "13:00", "14:00", people=("maya", "jordan"))
ev("personal", "Dentist", d(-1, 1), "08:30", "09:00", location="Smile Studio, Angel")
ev("work", "Offsite prep", d(-1, 1), "13:00", "14:30", people=("maya", "lea"))
ev("personal", "Climbing", d(-1, 2), "19:00", "21:00", location="The Castle Climbing Centre")
ev("work", "All-hands", d(-1, 3), "16:00", "17:00", meet=True, people=("maya", "jordan", "priya"))
ev("personal", "Cinema: Dune Part Three", d(-1, 3), "20:00", "22:45", location="Prince Charles Cinema")
ev("family", "Lunch at Dad's", d(-1, 6), "13:00", "15:30")
ev("work", "Roadmap review", d(1, 1), "11:00", "12:00", people=("jordan", "lea"))
ev("personal", "Haircut", d(1, 2), "18:00", "18:45")
ev("work", "All-hands", d(1, 3), "16:00", "17:00", meet=True, people=("maya", "jordan", "priya"))
ev("personal", "Weekend in Edinburgh", d(1, 4), end_day=d(1, 6))
ev("personal", "Train to Edinburgh", d(1, 4), "16:30", "21:00", location="London King's Cross")
ev("work", "Board prep", d(2, 0), "14:00", "15:30", people=("maya",))
ev("personal", "Book club", d(2, 2), "19:00", "21:00", location="Libreria, Spitalfields")
ev("holidays", "Movie night", d(2, 5))
ev("personal", "Housewarming party", d(2, 5), "20:00", "23:30", location="Alex's place")
ev("personal", "Climbing", d(3, 1), "19:00", "21:00", location="The Castle Climbing Centre")
ev("holidays", "Public holiday", d(3, 0))
ev("family", "Visit grandpa", d(3, 5), "14:00", "17:00")
ev("work", "Web Summit", d(4, 0), end_day=d(4, 3))

# --- Write --------------------------------------------------------------------
if ROOT.exists():
    shutil.rmtree(ROOT)
for cal, (name, color) in CALENDARS.items():
    (ROOT / cal / ".caldir").mkdir(parents=True)
    (ROOT / cal / ".caldir/config.toml").write_text(
        f'name = "{name}"\ncolor = "{color}"\nread_only = false\n')

for e in events:
    stamp = f"{e['day']:%Y-%m-%d}" + (f"T{e['start'].replace(':', '')}" if e["start"] else "")
    path = ROOT / e["cal"] / f"{stamp}__{slug(e['title'])}.ics"
    path.write_text(to_ics(e), newline="")
print(f"Wrote {len(events)} events around the week of {MON:%a %-d %b %Y} ({TZID}) to {ROOT}")
