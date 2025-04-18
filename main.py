import httpx
import json
from fastapi import FastAPI, HTTPException
from datetime import datetime
from typing import Dict, Any, Optional, List
import uvicorn
import random
import asyncio
from functools import lru_cache
import logging


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Instagram API", description="API for Instagram data retrieval")

# Cache proxies for 30 minutes to avoid excessive requests
@lru_cache(maxsize=1)
def get_cached_proxies(timestamp: int):
    """Cache proxies with a timestamp to force refresh every 30 minutes"""
    return []  # Initial empty list

async def fetch_proxies() -> List[str]:
    """Fetch fresh proxy list from the provided URL"""
    # Force refresh of cache every 30 minutes
    cache_timestamp = int(datetime.now().timestamp() / 1800)
    cached_proxies = get_cached_proxies(cache_timestamp)
    
    if cached_proxies:
        logger.info(f"Using {len(cached_proxies)} cached proxies")
        return cached_proxies
    
    url = "https://vakhov.github.io/fresh-proxy-list/http.txt"
    try:
        logger.info("Fetching new proxy list...")
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Parse the proxies (one per line in format IP:PORT)
            proxies = [line.strip() for line in response.text.split('\n') if line.strip()]
            logger.info(f"Fetched {len(proxies)} proxies")
            
            # Update cache
            get_cached_proxies.cache_clear()
            get_cached_proxies(cache_timestamp).extend(proxies)
            
            return proxies
    except Exception as e:
        logger.error(f"Error fetching proxies: {str(e)}")
        return []

def get_random_proxy() -> Optional[str]:
    """Get a random proxy from the cached list"""
    proxies = get_cached_proxies(int(datetime.now().timestamp() / 1800))
    if proxies:
        return random.choice(proxies)
    return None

async def make_request_with_proxy(url: str, headers: Dict[str, str], params: Dict[str, str] = None) -> Dict:
    """Make an HTTP request using rotating proxies with retry logic"""
    max_attempts = 3
    attempt = 0
    errors = []
    
    while attempt < max_attempts:
        proxy = get_random_proxy()
        proxies = {}
        
        if proxy:
            proxies = {
                "http://": f"http://{proxy}",
                "https://": f"http://{proxy}"
            }
            logger.info(f"Using proxy: {proxy}")
        else:
            logger.warning("No proxies available, making direct request")
        
        try:
            async with httpx.AsyncClient(proxies=proxies) as client:
                if params:
                    response = await client.get(url, headers=headers, params=params)
                else:
                    response = await client.get(url, headers=headers)
                
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"Request failed with proxy {proxy}: {str(e)}")
            errors.append(str(e))
            attempt += 1
            
    raise HTTPException(status_code=500, detail=f"All requests failed after {max_attempts} attempts: {', '.join(errors)}")

async def get_user_id(username: str) -> Dict[str, Any]:
    """Get user information from Instagram API"""
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        # this is internal ID of an instegram backend app. It doesn't change often.
        "x-ig-app-id": "936619743392459",
        # use browser-like features
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "*/*",
    }
    try:
        # Make sure we have proxies available
        await fetch_proxies()
        
        # Use proxy-enabled request function
        data = await make_request_with_proxy(url, headers)
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
        # this is internal ID of an instegram backend app. It doesn't change often.
        "x-ig-app-id": "936619743392459",
        # use browser-like features
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "*/*",
    }
    
    try:
        # Use proxy-enabled request function
        data = await make_request_with_proxy(url, headers, params)
        
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


# Add a new endpoint to manually refresh proxies
@app.get("/refresh-proxies", response_model=Dict[str, Any])
async def refresh_proxies():
    """Manually refresh the proxy list"""
    get_cached_proxies.cache_clear()
    proxies = await fetch_proxies()
    return {"status": "success", "proxy_count": len(proxies)}


async def startup_event():
    """Fetch proxies on application startup"""
    await fetch_proxies()


@app.on_event("startup")
async def startup():
    """Register startup event"""
    asyncio.create_task(startup_event())


def main():
    print("Starting Instagram API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
