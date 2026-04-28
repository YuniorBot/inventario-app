from email.utils import formataddr

import boto3
from flask import current_app


def get_ses_client():
    client = current_app.extensions.get("ses_client")
    if client is None:
        region_name = current_app.config.get("AWS_REGION") or None
        client = boto3.client("ses", region_name=region_name)
        current_app.extensions["ses_client"] = client
    return client


def _get_sender() -> str:
    sender_email = current_app.config.get("AWS_SES_FROM_EMAIL")
    if not sender_email:
        raise RuntimeError("AWS_SES_FROM_EMAIL no esta configurado.")

    sender_name = (current_app.config.get("AWS_SES_FROM_NAME") or "").strip()
    if not sender_name:
        return sender_email

    return formataddr((sender_name, sender_email))


def send_html_email(recipient: str, subject: str, html_body: str, text_body: str) -> None:
    get_ses_client().send_email(
        Source=_get_sender(),
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {"Data": text_body, "Charset": "UTF-8"},
            },
        },
    )
