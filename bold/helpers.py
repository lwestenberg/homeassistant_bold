from datetime import datetime, timedelta


def convert_expiration_time_to_isoformat(expiration_time: str):
    return (
        datetime.strptime(expiration_time, "%Y-%m-%dT%H:%M:%S.%fZ") - timedelta(hours=3)
    ).isoformat()
