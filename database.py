import json
from pathlib import Path
import os
from typing_extensions import TypedDict

# Saving to files is not the best practice, this is a temporary solution till I figure a better way

directory = Path(os.getcwd())
# list of users and their information
users = {}
# key of the cache is the UUID, and value will be the entire data field
cache = {}

class UserInfo(TypedDict):
    email: str
    name: str
    timezone: str

def load_users():
    if users:
        return users
    else:
        with open("users.json", "r") as file:
            users = json.loads(file.read())
            return users

def save_users():
    with open("users.json", "w") as file:
        file.write(json.dumps(users))

def update_user(UUID: str, data: UserInfo):
    users[UUID] = data

def load_data(UUID: str) -> dict:
    """
    Loads the data of the UUID of the user
    """
    if UUID not in cache.keys():
        filepath = os.path.join(directory, UUID + ".json")
        if os.path.isfile(filepath):
            with open(filepath, "r") as file:
                data = json.loads(file.read())
                cache[UUID] = data
                return data
        else:
            raise FileNotFoundError
    else:
        return cache[UUID]
    
def save_data(UUID, data: dict):
    """
    Saves a specific profile. Also updates the cache to prevent data conflicts
    """
    filepath = os.path.join(directory, UUID + ".json")
    with open(filepath, "w") as file:
        file.write(json.dumps(data))
    cache[UUID] = data

def save():
    """
    Purpose:
        Saves the entire cache, to be used on shutdown
    """
    for k,v in cache.items():
        filepath = os.path.join(directory, k + ".json")
        with open(filepath, "w") as file:
            file.write(json.dumps(v))

def update(UUID, data: dict):
    """
    Updates the cache of the specific UUID
    """
    cache[UUID] = data

if __name__ == "__main__":
    print(load_data("example"))