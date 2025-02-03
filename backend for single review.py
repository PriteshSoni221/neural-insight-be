from flask import Flask, request, jsonify
import openai
import json

app = Flask(__name__)

openai.api_key = "key in jira"

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
                You are an assistant that extracts sentiments for product reviews.
                The user text may be in English, German, or a mixture of both.

                Rules for final language output:
                - If the entire text is in German, respond in German.
                - If the entire text is in English, respond in English.
                - If the text is a mixture of English and German, respond entirely in English.

                Always respond in valid JSON with exactly five keys: "delivery", "quality", "price", "packaging", and "service".
                For each key, provide:
                  - "text": the relevant portion of the review (in the chosen language),
                  - "sentiment": one of "positive", "negative", or "neutral".

                No extra keys, no extra text—only the JSON.

                Input: "{review_text}"
                Output:
            """
    return gpt_request(prompt)

def clean_response(response_text):

    response_text = response_text.strip()
    if response_text.startswith("```") and response_text.endswith("```"):
        response_text = response_text.strip("```")
    return response_text

def gpt_request(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        result = response["choices"][0]["message"]["content"]
        cleaned_result = clean_response(result)
        return json.loads(cleaned_result)
    except Exception as e:
        print(f"Error in GPT request: {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True, port=5001)
