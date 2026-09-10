from pydantic import BaseModel


class ProfileTarget(BaseModel):
    """A profile for the browser agent to visit.

    `url` defaults to the bundled mock feed so the connector always has a
    legal, stable target out of the box. Point it at a different URL only
    with your own authorized access to a real platform/profile.
    """

    handle: str
    platform: str
    url: str
