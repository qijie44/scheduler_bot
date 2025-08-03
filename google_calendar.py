import os.path
import pickle
import configparser

from typing import TypedDict, NotRequired
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

class DateTime(TypedDict):
    datetime: str # datetime string with .isoformat
    timeZone: str

class EventInfo(TypedDict):
    location: NotRequired[str]
    start: NotRequired[DateTime]
    end: NotRequired[DateTime]
    summary: NotRequired[str]
    description: NotRequired[str]

config = configparser.ConfigParser()
config.read("bot.ini")
CALENDAR = config["CALENDAR"]["ID"]

SCOPES = ['https://www.googleapis.com/auth/calendar']

creds = None

if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)

    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

service = build('calendar', 'v3', credentials=creds)

def create_event(event: EventInfo) -> dict:
    created_event = service.events().insert(calendarId=CALENDAR, body=event).execute()
    return created_event

def modify_event(event_id: str, update: EventInfo) -> dict:
    event = service.events().get(calendarId=CALENDAR, eventId=event_id)
    for k,v in update.items():
        if v != None:
            event[k] = v
    updated_event = service.events().update(calendarId=CALENDAR, eventId=event['id'], body=updated_event).execute()
    return updated_event

def remove_event(event_id: str):
    service.events().delete(calendarId=CALENDAR, eventId=event_id).execute()
    return True