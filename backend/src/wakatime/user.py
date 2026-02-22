from uuid import UUID

from pydantic import BaseModel
import aiohttp

from . import WakatimeTokens

class UserCityModel(BaseModel):
    country_code: str
    name: str
    state: str
    title: str

class UserResponse(BaseModel):
    # https://wakatime.com/developers#users
    id: str
    bio: str | None
    has_premium_features: bool
    display_name: str
    full_name: str
    email: str
    photo: str
    is_email_public: bool
    is_photo_public: bool
    is_email_confirmed: bool
    public_email: str | None
    timezone: str
    last_heartbeat_at: str
    last_plugin: str
    last_plugin_name: str
    last_project: str
    last_branch: str
    plan: str
    username: str
    website: str
    human_readable_website: str
    wonderfuldev_username: str
    github_username: str
    twitter_username: str
    linkedin_username: str
    city: UserCityModel
    logged_time_public: bool
    languages_used_public: bool
    editors_used_public: bool
    categories_used_public: bool
    os_used_public: bool
    is_hireable: bool
    created_at: str
    modified_at: str

class UserResponseModel(BaseModel):
    data: UserResponse

async def get_current_user(
    tokens: WakatimeTokens
) -> UserResponse:
    """
    Returns information about the current user (who owns the WakatimeTokens)
    """

    async with aiohttp.ClientSession() as cs:
        async with cs.get(
            "https://wakatime.com/api/v1/users/current",
            headers = {
                "Authorization": f"Bearer {tokens['access_token']}"
            }
        ) as resp:
            resp_json = await resp.read()

    user_resp_model = UserResponseModel.model_validate_json(resp_json)

    return user_resp_model.data

async def get_user(
    tokens: WakatimeTokens,
    uuid: UUID
) -> UserResponse | None:
    """
    Returns information about the user specified, returns None if no
    user with the provided UUID exists
    """

    async with aiohttp.ClientSession() as cs:
        async with cs.get(
            f"https://wakatime.com/api/v1/users/{str(uuid)}",
            headers = {
                "Authorization" : f"Bearer {tokens['access_token']}"
            }
        ) as resp:
            
            if resp.status != 200:
                return None
            
            resp_json = await resp.read()

    user_resp_model = UserResponseModel.model_validate_json(resp_json)

    return user_resp_model.data