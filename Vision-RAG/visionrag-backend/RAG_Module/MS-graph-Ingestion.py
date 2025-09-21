# Temporary placeholder
class Graph:
    def __init__(self, config):
        self.settings = config
        
import asyncio
import configparser
from msgraph.generated.models.o_data_errors.o_data_error import ODataError


async def main():
    print('Python Graph Tutorial\n')

    # Load settings
    config = configparser.ConfigParser()
    config.read(['config.cfg', 'config.dev.cfg'])
    azure_settings = config['azure']

    graph: Graph = Graph(azure_settings)

    await greet_user(graph)

    choice = -1

    while choice != 0:
        print('Please choose one of the following options:')
        print('0. Exit')
        print('1. Display access token')
        print('2. List my inbox')
        print('3. Send mail')
        print('4. Make a Graph call')

        try:
            choice = int(input())
        except ValueError:
            choice = -1

        try:
            if choice == 0:
                print('Goodbye...')
            elif choice == 1:
                await display_access_token(graph)
            elif choice == 2:
                await list_inbox(graph)
            elif choice == 3:
                await send_mail(graph)
            elif choice == 4:
                await make_graph_call(graph)
            else:
                print('Invalid choice!\n')
        except ODataError as odata_error:
            print('Error:')
            if odata_error.error:
                print(odata_error.error.code, odata_error.error.message)


"""
Ingest Teams data (messages/files) into vector DB using Microsoft Graph API and existing ingestion logic.
"""
import os
import asyncio
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

from . import db, embed

# Load environment variables for MS Graph
load_dotenv()
MS_GRAPH_TOKEN = os.getenv("MS_GRAPH_TOKEN")  # Bearer token for Graph API
TEAM_ID = os.getenv("MS_TEAM_ID")             # Team ID to fetch data from
CHANNEL_ID = os.getenv("MS_CHANNEL_ID")       # Channel ID to fetch messages

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def get_headers():
    return {
        "Authorization": f"Bearer {MS_GRAPH_TOKEN}",
        "Content-Type": "application/json"
    }


def fetch_channel_messages(team_id: str, channel_id: str) -> List[Dict]:
    url = f"{GRAPH_API_BASE}/teams/{team_id}/channels/{channel_id}/messages"
    resp = requests.get(url, headers=get_headers())
    resp.raise_for_status()
    data = resp.json()
    return data.get("value", [])


async def ingest_teams_messages(team_id: str = TEAM_ID, channel_id: str = CHANNEL_ID):
    pool = db.get_pool()
    messages = fetch_channel_messages(team_id, channel_id)
    for msg in messages:
        text = msg.get("body", {}).get("content", "")
        if not text.strip():
            continue
        # Embed and insert using existing logic
        embedding = embed.embed_text_one(text, task_type="RETRIEVAL_DOCUMENT")
        await db.insert_text_chunk(
            doc_id=msg.get("id"),
            text=text,
            embedding=embedding,
            meta={"source": "teams", "from": msg.get("from", {})}
        )

# Optionally, add similar logic for files/attachments if needed

if __name__ == "__main__":
    asyncio.run(ingest_teams_messages())