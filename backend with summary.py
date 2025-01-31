from flask import Flask, request, jsonify
from pymongo import MongoClient
import openai
import json

app = Flask(__name__)

MONGO_URI = "mongodb+srv://user1:1234@cluster0.63cfp.mongodb.net"
client = MongoClient(MONGO_URI)

customer_db = client["customer_db"]
user_review_collection = customer_db["user_review"]

openai.api_key = "find jira"

@app.route('/')
def home():
    return "Hey!"

@app.route('/upload_reviews', methods=['POST'])
def upload_reviews():
    try:
        data = request.json
        product_id = data.get("productID")
        reviews = data.get("fileContent", {}).get("reviews", [])

        if not product_id or not reviews:
            return jsonify({"error": "Product ID and reviews are required"}), 400

        analyzed_reviews = []
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}

        for review_text in reviews:
            sentiment_result = analyze_sentiment(review_text)

            if sentiment_result and isinstance(sentiment_result, dict):
                analysis_result = {
                    "input": review_text,
                    "output": sentiment_result,
                    "history": []
                }
                analyzed_reviews.append(analysis_result)

                for category, sentiment_data in sentiment_result.items():
                    sentiment_counts[sentiment_data.get("sentiment", "neutral")] += 1

                inserted_review = user_review_collection.insert_one({
                    "product_id": product_id,
                    "review": analysis_result
                })

                analysis_result["_id"] = str(inserted_review.inserted_id)
            else:
                return jsonify({"error": "Sentiment analysis failed"}), 500

        summary = generate_summary(sentiment_counts)

        return jsonify({
            "productID": product_id,
            "analyzed_reviews": analyzed_reviews,
            "summary": summary
        }), 200

    except Exception as e:
        print(f"Error in upload_reviews: {e}")
        return jsonify({"error": "An error occurred while processing reviews"}), 500


def generate_summary(sentiment_counts):
    prompt = f"""
        You are summarizing customer feedback based on sentiment analysis. Here are the statistics:
        - Positive mentions: {sentiment_counts['positive']}
        - Negative mentions: {sentiment_counts['negative']}
        - Neutral mentions: {sentiment_counts['neutral']}

        **Instructions:**
        1. Mention key positive aspects if positive mentions are high.
        2. Highlight major negative concerns.
        3. Explain what neutral feedback suggests.
        4. Provide an **actionable recommendation** for improvement.

        **Output Format (strict JSON only, no additional text):**
        {{
            "summary": "Customers appreciate [positive aspect], but some report issues with [negative aspect]. The high number of neutral mentions suggests [explanation]. Improving [specific concern] may shift more neutral buyers to a positive experience."
        }}
    """
    result = gpt_request(prompt)
    return result.get("summary", "Summary generation failed") if isinstance(result,dict) else "Summary generation failed"


def analyze_sentiment(review_text):
    prompt = f"""
        You are an assistant that extracts sentiments for reviews.
        Always respond in JSON format with the following categories: delivery, quality, price, packaging, and service.
        For each category, provide:
        - The relevant text from the review.
        - The sentiment (positive, negative, or neutral).
        Respond strictly in JSON format with no extra text.
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
            max_tokens=200
        )
        result = response["choices"][0]["message"]["content"].strip()

        try:
            return json.loads(result)  # Convert GPT response to dictionary
        except json.JSONDecodeError:
            print(f"GPT response is not JSON: {result}")
            return {"error": "Invalid response from AI"}

    except Exception as e:
        print(f"Error in GPT request: {e}")
        return {"error": "Unable to process request"}

if __name__ == '__main__':
    app.run(debug=True, port=5002)
