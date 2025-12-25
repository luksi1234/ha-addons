#!/usr/bin/with-contenv bashio
set -e
bashio::log.info "Running add-on install tasks (if any)"
# Add any heavy one-time steps here (e.g., apt-get install of extra packages)
# For this skeleton, nothing is required at install time.
