import gradio as gr
from transformers import pipeline

# Load FinBERT model
pipe = pipeline("text-classification", model="ProsusAI/finbert", return_all_scores=True)

def predict(text):
    """
    Predict sentiment for financial text.
    Returns: Dict of probs, Label string, Score float
    """
    try:
        results = pipe(text)[0]
        # FinBERT labels: positive, negative, neutral
        scores = {item['label']: item['score'] for item in results}
        
        # Translate keys to Portuguese match Dashboard
        # Dashboard expects: Positivo, Negativo, Neutro
        mapped_scores = {
            "Positive": scores.get("positive", 0),
            "Negative": scores.get("negative", 0),
            "Neutral": scores.get("neutral", 0),
            # Add PT keys just in case
            "Positivo": scores.get("positive", 0),
            "Negativo": scores.get("negative", 0),
            "Neutro": scores.get("neutral", 0),
        }

        # Determine winner
        best_label = max(scores, key=scores.get)
        best_score = scores[best_label]
        
        # Format label
        label_map = {
            "positive": "Positivo 📈",
            "negative": "Negativo 📉",
            "neutral": "Neutro ➖"
        }
        final_label = label_map.get(best_label, best_label)
        
        if best_label == "negative":
            best_score = -best_score
        elif best_label == "neutral":
            best_score = 0.0

        return mapped_scores, final_label, best_score

    except Exception as e:
        return {"Error": 1.0}, f"Error: {str(e)}", 0.0

# Create Interface
# By default, gr.Interface creates an api named '/predict'
iface = gr.Interface(
    fn=predict,
    inputs=gr.Textbox(lines=3, placeholder="Enter financial text here..."),
    outputs=[
        gr.Label(label="Probabilities"), 
        gr.Label(label="Sentiment"), 
        gr.Number(label="Sentiment Score")
    ],
    title="Sentix FinBERT API",
    description="Financial Sentiment Analysis Model (FinBERT)",
    examples=[
        ["Petrobras anuncia lucro recorde."],
        ["Inflação sobe acima do esperado."],
        ["Banco Central mantém taxa Selic."]
    ]
)

if __name__ == "__main__":
    iface.launch()
