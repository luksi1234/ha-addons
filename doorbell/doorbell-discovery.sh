#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# ==============================================================================
# Send OTBR discovery information to Home Assistant
# ==============================================================================
declare config

bashio::log.info "$(bashio::addon.hostname)"
bashio::log.info "$(bashio::config 'port')"

bashio::log.info "11111111"

config=$(bashio::var.json \
    host "$(bashio::addon.hostname)" \
    port2 "^8081" \
    port "$(bashio::config 'port')" \
    firmware "12345" \
)

bashio::log.info "22222222"

# Send discovery info
if bashio::discovery "doorbell" "${config}" > /dev/null; then
    bashio::log.info "Successfully sent discovery information to Home Assistant."
else
    bashio::log.error "Discovery message to Home Assistant failed!"
fi
