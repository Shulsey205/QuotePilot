import requests

API_URL = "http://127.0.0.1:8000/quote"


def call_quote_api(part_number: str):
    payload = {"part_number": part_number}

    response = requests.post(API_URL, json=payload)

    print(f"Status code: {response.status_code}")
    print("Response JSON:")
    print(response.json())


if __name__ == "__main__":
    print("Valid part number test")
    call_quote_api("QPSAH200S-A-M-G-3-C-3-1-1-C-1-02")

    print("\nInvalid part number test")
    call_quote_api("QPSAH200S-Z-M-G-3-C-3-1-1-C-1-02")
