FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3 py3-cryptography py3-pillow py3-google-auth py3-requests tzdata
WORKDIR /app
COPY server.py origin_configuration.py panel_actions.py policy.py oauth_meta.py panel_login.py instagram_connection.py account_avatar.py sender_profiles.py account_registry.py account_management.py editorial_core.py editorial_http.py editorial_import.py editorial_connections.py editorial_multi_api.py editorial_drive.py editorial_graph.py editorial_delivery.py editorial_publishing.py editorial_history.py interface_ui.py interface-ui.js interface-ui.css /app/
COPY editorial-ui/ /app/editorial-ui/
COPY tests/ /app/tests/
COPY tools/ /app/tools/
COPY proxy/instagram.conf /app/proxy/instagram.conf
COPY config.yaml /app/config.yaml
# Focused security gate: synthetic registry, mocked Drive and loopback HTTP.
# No live credentials, Meta, external calls or production data.
RUN python3 -m py_compile server.py origin_configuration.py panel_actions.py policy.py oauth_meta.py panel_login.py instagram_connection.py account_avatar.py sender_profiles.py account_registry.py account_management.py editorial_core.py editorial_http.py editorial_import.py editorial_connections.py editorial_multi_api.py editorial_drive.py editorial_graph.py editorial_delivery.py editorial_publishing.py editorial_history.py interface_ui.py
RUN python3 -m unittest discover -s tests -p test_editorial_connections.py && python3 -m unittest discover -s tests -p test_editorial_drive.py && python3 -m unittest discover -s tests -p test_editorial_multi_http.py && python3 -m unittest discover -s tests -p test_interface_ui.py && python3 -m unittest discover -s tests -p test_settings_navigation.py
CMD ["python3", "-u", "/app/server.py"]
