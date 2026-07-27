"""Whitelisted report endpoints, including chart image rendering."""

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_chart_png(
	dataset: list[dict],
	title: str = "",
	x_key: str = "label",
	y_key: str = "value",
) -> bytes:
	labels = [str(row.get(x_key, "")) for row in dataset]
	values = [row.get(y_key, 0) for row in dataset]

	fig, ax = plt.subplots(figsize=(6, 4))
	ax.bar(labels, values, color="#4C72B0")
	ax.set_title(title)
	ax.set_ylabel("Amount")
	plt.xticks(rotation=30, ha="right")
	fig.tight_layout()

	buffer = io.BytesIO()
	fig.savefig(buffer, format="png")
	plt.close(fig)
	buffer.seek(0)
	return buffer.getvalue()