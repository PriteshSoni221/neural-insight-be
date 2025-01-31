from flask import Flask, request, jsonify
import openai

app = Flask(__name__)


openai.api_key = "find in jira"

@app.route('/')
def home():
    return "single!"


@app.route('/analyze_review', methods=['POST'])
def analyze_review():
    try:
        data = request.json
        review_text = data.get("review")

        if not review_text:
            return jsonify({"error": "Review text is required"}), 400


        sentiment_result = analyze_sentiment(review_text)

        if sentiment_result:
            return jsonify({
                "input": review_text,
                "output": sentiment_result
            }), 200
        else:
            return jsonify({"error": "Sentiment analysis failed"}), 500

    except Exception as e:
        print(f"Error in analyze_review: {e}")
        return jsonify({"error": "An error occurred while processing the review"}), 500

def analyze_sentiment(review_text):
    prompt = f"""
        You are an assistant that extracts sentiments for a single review. Break the input into the categories:
        delivery, quality, price, packaging, and service.
        For each category, provide:
        - The text related to the category.
        - The sentiment (positive, negative, or neutral).
        Respond in JSON format only.
        Input: "{review_text}"
        Output:
    """
    return gpt_request(prompt)


def gpt_request(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        result = response["choices"][0]["message"]["content"]
        return eval(result)  # Convert JSON string to dictionary
    except Exception as e:
        print(f"Error in GPT request: {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True, port=5001)
