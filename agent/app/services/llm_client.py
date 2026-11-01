import os
from typing import Any

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import BaseMessage


def get_model_name() -> str:
    model = os.getenv(
        "LITELLM_MODEL",
        "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    )
    return model.removeprefix("bedrock/")


def get_bedrock_converse_llm(**kwargs: Any) -> ChatBedrockConverse:
    model = kwargs.pop("model", get_model_name())
    return ChatBedrockConverse(
        model=model,
        region_name=kwargs.pop("region_name", os.getenv("AWS_REGION", "us-east-1")),
        temperature=kwargs.pop("temperature", 0),
        max_tokens=kwargs.pop("max_tokens", 4096),
        **kwargs,
    )


def invoke_llm(messages: list[BaseMessage], **kwargs: Any) -> Any:
    bedrock_messages = []
    for message in messages:
        if isinstance(message, dict):
            bedrock_messages.append(message)
            continue
        role = message.type
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        bedrock_messages.append({"role": role, "content": message.content})
    llm = get_bedrock_converse_llm(**kwargs)
    return llm.invoke(bedrock_messages)
