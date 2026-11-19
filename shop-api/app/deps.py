# Placeholder authentication: the caller sends their user id in a header.
# Replace with real JWT/OAuth2 auth later; the tests won't need to change much.
from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: int | None = Header(default=None)) -> int:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return x_user_id
