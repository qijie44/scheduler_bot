from typing import TypedDict, Annotated, Sequence, Union
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, InjectedState
from datetime import datetime, timedelta
from langchain_core.runnables import RunnableConfig
import pprint
import json
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import configparser
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
import os.path
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

config = configparser.ConfigParser()
config.read("bot.ini")

SCOPES = ['https://www.googleapis.com/auth/calendar']

TELEGRAM_TOKEN = config["KEYS"]["BOT_TOKEN"]

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    location: str
    start_date: str
    start_time: str
    duration: int
    description: str
    user: Union[int, str] # TODO: update when we get the user to save their names

model = ChatOllama(
    model="llama3.1",
    temperature=0.1,
)

@tool
def create_event(state: Annotated[dict, InjectedState]) -> str:
    """
    Purpose:
        Create an event with the information given. Use after successfully using set_meeting_datetime tool

    Args:
        state (dict): The current LangGraph state, injected at runtime. Ensure that location, start time and duration are not none
    """
    print("---Create event here---")
    pprint.pp(state)
    failed_flag = False
    event = {
        "summary": "",
        "location": "",
        "description": "",
        "start": {
            "dateTime": "",
            "timeZone": "Europe/London"
        },
        "end": {
            "dateTime": "",
            "timeZone": "Europe/London"
        }
    }
    response = "Failed to create event due to the following reasons:\n"
    if state["location"] == None:
        response += "- Location is missing\n"
        failed_flag = True
    if state["start_time"] == None:
        response += "- start time is missing\n"
        failed_flag = True
    if state["start_date"] == None:
        response += "- start date is missing\n"
        failed_flag = True
    if state["duration"] == None:
        response += "- duration is missing\n"
        failed_flag = True
    if not failed_flag:
        event["location"] = state["location"]
        date_str = f'{state["start_date"]} {state["start_time"]}'
        event["start"]["dateTime"] = datetime.strptime(date_str, '%d/%m/%Y %H:%M').isoformat()
        event["end"]["dateTime"] = (datetime.strptime(date_str, '%d/%m/%Y %H:%M') + timedelta(minutes=state["duration"])).isoformat()
        event["summary"] = f"Meeting with {str(state["user"])}"
        response = f"Meeting has been successfully scheduled on {str(state['start_date'])} {str(state['start_time'])} at {state['location']} for {state['duration']} mins"
        if state["description"] != None:
            response += f"the information for the meeting are as follows: \n {state['description']}"
        created_event = service.events().insert(calendarId=config["CALENDAR"]["ID"], body=event).execute()
        print(f"Created event: {created_event['id']}")
    
    message = AIMessage(response)
    return {"messages": message}

@tool
def set_description(description: str):
    """
    Purpose:
        Set the description of the meeting

    Args:
        description: description of the meeting as a string
    """
    print(description)
    return {"description": description}

@tool
def set_location(location: str) -> dict:
    """
    Purpose:
        Set the location of the meeting

    Args:
        location: location of the meeting as a string
    """
    return {"location": location}

# @tool
# def set_meeting_date_from_day(state: Annotated[dict, InjectedState]) -> dict:
#     """
#     Purpose:
#         Determines the number of days until a future meeting date based on user input and sets start_date with it
        
#     Args:
#         state (dict): The current LangGraph state, injected at runtime.
#     """
#     for message in reversed(state["messages"]):
#         if isinstance(message, HumanMessage):
#             information = message.content
#     query = f"""the information of the meeting are as follows. {information}. The date is {datetime.now().strftime('%d/%m/%Y')}. 
#                  It is currently a {datetime.now().strftime('%A')}. How many days is the meeting in?. Respond with a single number and nothing else"""
#     print(query)
#     response = model.invoke(query)
#     print(response)
#     try:
#         return {"start_date":(datetime.now() + timedelta(days=int(response.content))).strftime('%d/%m/%Y')}
#     except Exception as e:
#         print(f"Response error: {e}")    

@tool
def set_meeting_date_from_date(date: str) -> dict:
    """
    Purpose:
        Set the meeting in a future date and time.

    Args:
        date (str): The date of the meeting, in dd/mm/yyyy format
    """
    try:
        datetime.strptime(f"{date}", r"%d/%m/%Y")
        return {
                "start_date": date
                }
    except:
        return "datetime has to be in dd/mm/yyyy format!"

@tool
def set_meeting_time(time:str) -> dict:
    """
    Purpose:
        Start_time value of the state
        
    Args:
        time (str): The time of the meeting, in hh:mm format
    """
    return {"start_time": time}

@tool
def set_duration( minutes: int) -> dict:
    """
    Purpose:
        Set the duration of the meeting in minutes

    Args:
        minutes (int): The duration of the meeting in minutes
    """
    return {"duration": minutes}

tools = [create_event, set_location, set_meeting_date_from_date, set_duration, set_meeting_time]

llm = ChatOllama(
    model="llama3-groq-tool-use",
    temperature=0.1,
).bind_tools(tools)

def scheduler_agent(state: AgentState) -> AgentState:
    system_prompt = SystemMessage(f"""
        You are scheduler, a helpful scheduling assistant. You are going to help the user schedule meetings 
        by asking for location, start time and duration of the meetings. You will then create an event based on the information using the create_event tool
        given. Format all dates in dd/mm/yyyy format. The date today is {datetime.now()}

        - If the user wants to set a meeting in the future, use the set_meeting_datetime tool to set the start datetime of the future meeting.
        - If the user wants to set a meeting a future day but does not provide the date, ask the user for the date in dd/mm/yyyy format
        - Once you have the date and time of the meeting, use set_meeting_date tool set_meeting_time tool before calling the create event tool
        - When the user gives the duration, use set_duration tool to set the duration
        - When the user gives the location, use set_location tool to set the duration
        - When all the information (e.g. location, start time, duration) of the meeting is fixed, use the create_event tool to schedule the meeting
        - The meeting is not scheduled until the create_event tool is run successfully
        - When the create_event tool is called successfully, return the AImessage and end the conversation""")
        

    if not state["messages"]: 
        state["messages"] = [AIMessage("I'm ready to help you schedule a meeting. When and where will it be? How long will it take?")]
    else:
        if isinstance(state["messages"][-1], HumanMessage):
            user_message = state["messages"][-1]
        all_messages = [system_prompt] + list(state["messages"])
        response = llm.invoke(all_messages)
        print(f"\n AI: {response.content}")
    
        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")

        if not isinstance(state["messages"][-1], ToolMessage):
            state["messages"] = state["messages"] + [user_message, response]
        else:
            state["messages"] = state["messages"] + [response]
    return state

def should_continue(state: AgentState) -> str:
    """Determine if we should continue or end the conversation"""
    messages = state["messages"]

    if not messages:
        return "continue"

    if "scheduled" in messages[-1].content.lower() and "meeting" in messages[-1].content.lower():
       return "end"
    else:
        return "continue"
    
# post processing node to apply changes to state
def merge_tool_output(state: AgentState) -> AgentState:
    last = state["messages"][-1]
    if isinstance(last, ToolMessage):
        try:
            # Parse content from ToolMessage
            updates = json.loads(last.content)
            if isinstance(updates, dict):
                state.update(updates)
        except Exception as e:
            print(f"Error merging tool output: {e}")
    return state

def print_messages(messages):
    """Function to print the messages in a more readable format"""
    if not messages:
        return
    
    for message in messages[-3:]:
        if isinstance(message, ToolMessage):
            print(f"TOOL CALL: {message.content}")

# graph starts here
graph = StateGraph(AgentState)

graph.add_node("agent_node", scheduler_agent)
graph.add_node("tool_node", ToolNode(tools))
graph.add_node("merge_tool_output_node", merge_tool_output)

# graph.add_edge("agent_node", "tool_node")
graph.add_edge("tool_node", "merge_tool_output_node")
graph.add_edge("merge_tool_output_node", "agent_node")
graph.add_conditional_edges(
    "agent_node",
    should_continue,
    {
        "continue": "tool_node",
        "end": END,
    }
)

graph.add_edge(START, "agent_node")

app = graph.compile()

# Code to save the graph
image = app.get_graph().draw_mermaid_png()
with open("new_graph.png", "wb") as file:
    file.write(image)

bot = Application.builder().token(TELEGRAM_TOKEN).build()
user_states: dict[int, AgentState, str] = {}  # per‑user memory

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    # Initialize or retrieve state
    state = user_states.setdefault(chat_id, {"messages": [],
                                            "location": None,
                                            "start_time": None,
                                            "start_date": None,
                                            "duration": None,
                                            "description": None,
                                            "user": update.effective_chat.id,
                                            })

    # Append user's message
    state["messages"].append(HumanMessage(content=text))

    # Run through LangGraph
    for event in app.stream(state):
        for v in event.values():
            state = v
            reply = v["messages"][-1]
        print(f"reply: {reply}")
        if isinstance(reply, AIMessage) and hasattr(reply, "tool_calls") and not reply.tool_calls:
            print(f"reply: {reply}")
            await context.bot.send_message(chat_id=chat_id, text=reply.content)
            break  # stop after first response

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

bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    print("Bot running…")
    bot.run_polling()