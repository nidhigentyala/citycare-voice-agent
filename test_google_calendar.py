from backend.google_calendar import test_calendar_access


if __name__ == "__main__":
    try:
        result = test_calendar_access()

        print("Google Calendar connection successful!")
        print("Calendar name:", result["calendar_name"])
        print("Calendar ID:", result["calendar_id"])
        print("Time zone:", result["timezone"])

    except Exception as error:
        print("Google Calendar connection failed.")
        print("Error type:", type(error).__name__)
        print("Error details:", error)