def run_server():
    os.chdir(STATIC_DIR)
    # Use PORT from environment variable (Render sets this) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    with socketserver.TCPServer(("0.0.0.0", port), EMSRequestHandler) as httpd:
        print(f"Employee Management System Server running on http://0.0.0.0:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()