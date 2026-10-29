"""One bounded, idempotent conversation check; no orders or secret output."""

QUESTION = "Кратко объясни, что означает диверсификация инвестиционного портфеля. Не предлагай сделки."
MAX_COST_MICRO_RUB = 1_000_000


def usable(quote):
    cost = quote.get("cost_ceiling_micro_rub")
    return (quote.get("available") is True and type(cost) is int
            and 0 < cost <= MAX_COST_MICRO_RUB
            and quote.get("selected_tier") == "fast"
            and quote.get("requires_cost_confirmation") is not True)


def verify(api, request_id):
    result = {"status": "blocked", "sent": False, "completed": False,
              "user_messages": 0, "assistant_messages": 0, "answer_present": False}
    if not usable(api.estimate(QUESTION, None)):
        return result
    thread = api.thread(request_id + ".thread")
    quote = api.estimate(QUESTION, thread)
    if not usable(quote):
        return result
    job = api.send(thread, QUESTION, request_id, quote)
    result["sent"] = True
    api.run(job)
    state = api.state(job)
    result["completed"] = state == "completed"
    rows = [row for row in api.messages(thread) if row.get("request_id") == request_id]
    users = [row for row in rows if row.get("role") == "user"]
    assistants = [row for row in rows if row.get("role") == "assistant"]
    result.update(user_messages=len(users), assistant_messages=len(assistants),
                  answer_present=bool(assistants and assistants[0].get("text", "").strip()))
    if result["completed"] and len(users) == 1 and len(assistants) == 1 and result["answer_present"]:
        result["status"] = "verified"
    else:
        result["status"] = "incomplete"
    return result
