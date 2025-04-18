import httpx
import json
from fastapi import FastAPI, HTTPException
from datetime import datetime
from typing import Dict, Any, Optional
import uvicorn



app = FastAPI(title="Instagram API", description="API for Instagram data retrieval")

async def get_user_id(username: str) -> Dict[str, Any]:
    """Get user information from Instagram API"""
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "x-ig-app-id": "936619743392459"
    }
    try:
        response = await httpx.AsyncClient().get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["data"]
    except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user data: {str(e)}")


async def get_last_post_date(username: str) -> Optional[datetime]:
    """Get the date of the last post for a given Instagram username"""
    user_data = await get_user_id(username)
    user_id = user_data["user"]["id"]
    
    url = "https://www.instagram.com/graphql/query/"
    variables = {
        "id": user_id,
        "first": 1
    }
    params = {
        "query_hash": "58b6785bea111c67129decbe6a448951",
        "variables": json.dumps(variables)
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        response = await httpx.AsyncClient().get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        edges = data["data"]["user"]["edge_owner_to_timeline_media"]["edges"]
        if edges:
            timestamp = edges[0]["node"]["taken_at_timestamp"]
            return datetime.fromtimestamp(timestamp)
        else:
            return None
    except (httpx.HTTPError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to get post data: {str(e)}")


@app.get("/user/{username}")
async def user_info(username: str):
    """Get information about an Instagram user"""
    return await get_user_id(username)


@app.get("/last-post/{username}")
async def last_post(username: str):
    """Get the date of the last post for an Instagram user"""
    last_date = await get_last_post_date(username)
    if last_date:
        return {"username": username, "last_post_date": last_date.isoformat()}
    else:
        return {"username": username, "last_post_date": None, "message": "No posts found"}


def main():
    print("Starting Instagram API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
