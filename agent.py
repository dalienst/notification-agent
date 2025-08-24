from playwright.sync_api import sync_playwright, TimeoutError
import re
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Mock LLM for reasoning and UI inference
def mock_llm_reason(instruction, html_content, provider):
    """
    Mock LLM to interpret instruction and generate abstract steps.
    Returns a list of actions: [('action_type', params_dict)]
    Uses provider-specific hints if needed, but aims for generality.
    """
    # Parse instruction (simple regex for demo: "send email to {to} about {subject} saying '{body}'")
    match = re.match(
        r"send email to ([\w\.-]+@[\w\.-]+) about (.*) saying '(.+)'",
        instruction.lower(),
    )
    if not match:
        raise ValueError(
            "Invalid instruction format. Use: send email to email about subject saying 'body'"
        )
    to_email, subject, body = match.groups()

    # Provider-specific label mappings for robustness (minimal config)
    labels = {
        "gmail": {
            "compose_button": "Compose",
            "to_label": "To",
            "subject_label": "Subject",
            "body_label": "Message Body",
            "send_button": "Send",
        },
        "outlook": {
            "compose_button": "New message",
            "to_label": "To",
            "subject_label": "Add a subject",
            "body_label": "Message body",
            "send_button": "Send",
        },
    }.get(provider, {})

    if not labels:
        raise ValueError("Unsupported provider")

    # Generate abstract steps
    steps = [
        ("click_button", {"name": labels["compose_button"], "role": "button"}),
        ("fill_input", {"label": labels["to_label"], "value": to_email}),
        ("fill_input", {"label": labels["subject_label"], "value": subject}),
        ("fill_input", {"label": labels["body_label"], "value": body}),
        ("click_button", {"name": labels["send_button"], "role": "button"}),
    ]

    # Simulate DOM reasoning: Check if labels exist in HTML (for demo)
    for step in steps:
        if (
            "label" in step[1]
            and labels[step[1]["label"].lower()] not in html_content.lower()
        ):
            logging.warning(
                f"Label {step[1]['label']} not found in HTML, may need adjustment"
            )

    return steps


class GenericUIAgent:
    def __init__(self, provider):
        self.provider = provider
        self.url = {
            "gmail": "https://mail.google.com",
            "outlook": "https://outlook.live.com/mail/",
        }.get(provider)
        if not self.url:
            raise ValueError("Unsupported provider")
        self.page = None

    def execute(self, instruction):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False
            )  # For demo; use headless=True in prod
            self.page = browser.new_page()

            # Navigate and mock auth (in reality, handle login with credentials)
            self.page.goto(self.url)
            logging.info(f"Navigated to {self.provider} at {self.url}")
            # Mock auth: Assume logged in. Add real login:
            # self.page.get_by_label("Email or phone").fill("your_email")
            # self.page.get_by_label("Password").fill("your_pass")
            # self.page.get_by_role("button", name="Sign in").click()

            # Wait for load
            self.page.wait_for_load_state("networkidle")

            # Get HTML for LLM
            html = self.page.content().lower()  # Lower for case-insensitive

            # Get steps from mocked LLM
            steps = mock_llm_reason(instruction, html, self.provider)

            for action, params in steps:
                try:
                    if action == "click_button":
                        locator = self.page.get_by_role(
                            params["role"], name=params["name"], exact=False
                        )
                        locator.wait_for(state="visible", timeout=5000)
                        locator.click()
                        logging.info(f"Clicked button: {params['name']}")
                    elif action == "fill_input":
                        locator = self.page.get_by_label(params["label"], exact=False)
                        locator.wait_for(state="visible", timeout=5000)
                        locator.fill(params["value"])
                        logging.info(
                            f"Filled input {params['label']} with {params['value']}"
                        )
                    self.page.wait_for_timeout(2000)  # Delay for UI updates
                except TimeoutError:
                    logging.error(f"Timeout waiting for element: {params}")
                    # Recovery: Screenshot for debug
                    self.page.screenshot(path=f"error_{self.provider}.png")
                    raise  # Or continue with heuristic

            logging.info("Task completed successfully")
            browser.close()


# CLI example
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(
            "Usage: python agent.py \"send email to joe@example.com about Meeting saying 'Hello from automation'\" --provider gmail"
        )
        sys.exit(1)

    instruction = sys.argv[1]
    provider = sys.argv[3] if len(sys.argv) > 3 else "gmail"

    agent = GenericUIAgent(provider)
    agent.execute(instruction)
