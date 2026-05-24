# templates.py

from html import escape


DEBUG_FIELDS = [
    ("venue_name", "Venue", "text", "2"),
    ("venue_address", "Address", "text", "3"),
    ("date", "Date", "date", "4"),
    ("time", "Time", "time", "5"),
    ("party_size", "Party size", "number", "6"),
    ("condition", "Condition", "text", "7"),
    ("temperature_c", "Temperature C", "number", "8"),
    ("total_gbp", "Total GBP", "number", "9"),
    ("deposit_required_gbp", "Deposit required GBP", "number", "10"),
]


def render_flyer_html(event_details: dict) -> str:
    venue_name = escape(str(event_details["venue_name"]))
    venue_address = escape(str(event_details["venue_address"]))
    date = escape(str(event_details["date"]))
    time = escape(str(event_details["time"]))
    party_size = escape(str(event_details["party_size"]))
    condition = escape(str(event_details["condition"]))
    temperature_c = escape(str(event_details["temperature_c"]))
    total_gbp = escape(str(event_details["total_gbp"]))
    deposit_required_gbp = escape(str(event_details["deposit_required_gbp"]))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Edinburgh Pub Event Flyer</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 0;
      padding: 40px;
      background: #f7f3ea;
      color: #222;
    }}
    .flyer {{
      max-width: 760px;
      margin: 0 auto;
      background: #ffffff;
      border-radius: 16px;
      padding: 32px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    }}
    h1 {{
      margin-top: 0;
      font-size: 36px;
    }}
    h2 {{
      margin-top: 28px;
      border-bottom: 1px solid #ddd;
      padding-bottom: 8px;
    }}
    .fact {{
      margin: 10px 0;
      font-size: 18px;
    }}
    .label {{
      font-weight: bold;
    }}
  </style>
</head>
<body>
  <main class="flyer">
    <h1 data-testid="1">Edinburgh Pub Event</h1>

    <section>
      <h2>Venue</h2>
      <p class="fact"><span class="label">Venue:</span> <span data-testid="2">{venue_name}</span></p>
      <p class="fact"><span class="label">Address:</span> <span data-testid="3">{venue_address}</span></p>
      <p class="fact"><span class="label">Date:</span> <span data-testid="4">{date}</span></p>
      <p class="fact"><span class="label">Time:</span> <span data-testid="5">{time}</span></p>
      <p class="fact"><span class="label">Party size:</span> <span data-testid="6">{party_size}</span></p>
    </section>

    <section>
      <h2>Weather</h2>
      <p class="fact">
        Expected weather: <span data-testid="7">{condition}</span>,
        <span data-testid="8">{temperature_c}</span>°C
      </p>
    </section>

    <section>
      <h2>Cost Breakdown</h2>
      <p class="fact"><span class="label">Total cost:</span> £<span data-testid="9">{total_gbp}</span></p>
      <p class="fact"><span class="label">Deposit required:</span> £<span data-testid="10">{deposit_required_gbp}</span></p>
    </section>
  </main>
</body>
</html>
"""


def render_debug_flyer_html(event_details: dict) -> str:
    """Render flyer.html with live-editable event detail inputs."""
    flyer_html = render_flyer_html(event_details)
    inputs = "\n".join(
        (
            f'        <label>{escape(label)}'
            f' <input type="{input_type}" data-target-testid="{testid}" '
            f'name="{escape(key, quote=True)}" '
            f'value="{escape(str(event_details[key]), quote=True)}"></label>'
        )
        for key, label, input_type, testid in DEBUG_FIELDS
    )
    panel = f"""
  <aside class="debug-panel" aria-label="Debug event details">
    <h2>Event details input</h2>
    <form>
{inputs}
    </form>
  </aside>
"""
    debug_style = """
    .debug-panel {
      max-width: 760px;
      margin: 0 auto 24px;
      background: #102033;
      color: #ffffff;
      border-radius: 8px;
      padding: 20px;
    }
    .debug-panel h2 {
      margin: 0 0 16px;
      border: 0;
      padding: 0;
      font-size: 20px;
    }
    .debug-panel form {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }
    .debug-panel label {
      display: grid;
      gap: 6px;
      font-size: 14px;
      font-weight: bold;
    }
    .debug-panel input {
      box-sizing: border-box;
      width: 100%;
      border: 1px solid #9fb0c4;
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
    }
"""
    debug_script = """
  <script>
    document.querySelectorAll("[data-target-testid]").forEach((input) => {
      const update = () => {
        const target = document.querySelector(`[data-testid="${input.dataset.targetTestid}"]`);
        if (target) target.textContent = input.value;
      };
      input.addEventListener("input", update);
    });
  </script>
"""
    return (
        flyer_html.replace("  </style>", debug_style + "  </style>")
        .replace("<body>", "<body>" + panel)
        .replace("</body>", debug_script + "</body>")
    )
