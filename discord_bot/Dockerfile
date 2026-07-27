FROM python:3.11-slim

ARG S2PROTOCOL_REF=fbb98e80aee825d6deeabd7b48b51cbecebde062
ARG VCS_REF=unknown

LABEL org.opencontainers.image.source="https://github.com/hauomu/AOK-replay-lab" \
      org.opencontainers.image.revision="${VCS_REF}"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install --no-install-recommends --yes git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --requirement requirements.txt \
    && pip install --no-cache-dir mpyq \
       "s2protocol @ git+https://github.com/Blizzard/s2protocol.git@${S2PROTOCOL_REF}" \
    && apt-get purge --auto-remove --yes git \
    && rm -rf /var/lib/apt/lists/*

COPY src ./src

CMD ["python", "-m", "src.aok_bot.bot"]
