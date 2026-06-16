def build_graph():
    def invoke(payload):
        message = payload.get("message", "")
        return {"answer": f"compatibility example received: {message}"}

    return invoke
