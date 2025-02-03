from flask import Flask, request, jsonify
from pymongo import MongoClient
import openai
import json

app = Flask(__name__)
MONGO_URI = "mongodb+srv://user1:1234@cluster0.63cfp.mongodb.net"
client = MongoClient(MONGO_URI)
customer_db = client["customer_db"]
user_review_collection = customer_db["user_review"]
openai.api_key = "key in jira"


@app.route('/')
def home():
    return "Hey!"


@app.route('/upload_reviews', methods=['POST'])
def upload_reviews():
    try:
        data = request.json


        product_id_raw = data.get("productID")
        if product_id_raw is None:
            return jsonify({"error": "Missing productID"}), 400


        try:
            product_id = int(product_id_raw)
        except ValueError:
            return jsonify({"error": "Product ID must be an integer"}), 400

        reviews = data.get("fileContent", {}).get("reviews", [])
        if not reviews:
            return jsonify({"error": "No reviews provided"}), 400

        analyzed_docs = []
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}

        for review_obj in reviews:
            review_text = review_obj.get("text", "").strip()
            if not review_text:
                continue

            sentiment_result = analyze_sentiment(review_text)
            if not isinstance(sentiment_result, dict):
                return jsonify({"error": "Sentiment analysis failed"}), 500


            doc_to_insert = {
                "Product_id": product_id,
                "Text": review_text,
                "DeliveryText": sentiment_result["delivery"]["text"],
                "DeliverySentiment": sentiment_result["delivery"]["sentiment"],
                "QualityText": sentiment_result["quality"]["text"],
                "QualitySentiment": sentiment_result["quality"]["sentiment"],
                "PriceText": sentiment_result["price"]["text"],
                "PriceSentiment": sentiment_result["price"]["sentiment"],
                "PackagingText": sentiment_result["packaging"]["text"],
                "PackagingSentiment": sentiment_result["packaging"]["sentiment"],
                "ServiceText": sentiment_result["service"]["text"],
                "ServiceSentiment": sentiment_result["service"]["sentiment"]
            }
            
            for cat_data in sentiment_result.values():
                s = cat_data.get("sentiment", "neutral")
                sentiment_counts[s] += 1

            inserted = user_review_collection.insert_one(doc_to_insert)
            doc_to_insert["_id"] = str(inserted.inserted_id)
            analyzed_docs.append(doc_to_insert)

        summary = generate_summary(sentiment_counts)
        return jsonify({
            "productId": product_id,
            "analyzed_reviews": analyzed_docs,
            "summary": summary
        }), 200

    except Exception as e:
        print(f"Error in upload_reviews: {e}")
        return jsonify({"error": "An error occurred while processing reviews"}), 500


@app.route('/fetch_reviews', methods=['GET'])
def fetch_reviews():
    try:

        product_id_raw = request.args.get("productId")
        if not product_id_raw:
            return jsonify({"error": "Product ID is required"}), 400

        try:
            product_id = int(product_id_raw)
        except ValueError:
            return jsonify({"error": "Product ID must be an integer"}), 400

        reviews_cursor = user_review_collection.find({"Product_id": product_id})
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        fetched_reviews = []

        for doc in reviews_cursor:
            review_data = {
                "_id": str(doc["_id"]),
                "Product_id": doc.get("Product_id"),
                "Text": doc.get("Text", ""),
                "DeliveryText": doc.get("DeliveryText", ""),
                "DeliverySentiment": doc.get("DeliverySentiment", "neutral"),
                "QualityText": doc.get("QualityText", ""),
                "QualitySentiment": doc.get("QualitySentiment", "neutral"),
                "PriceText": doc.get("PriceText", ""),
                "PriceSentiment": doc.get("PriceSentiment", "neutral"),
                "PackagingText": doc.get("PackagingText", ""),
                "PackagingSentiment": doc.get("PackagingSentiment", "neutral"),
                "ServiceText": doc.get("ServiceText", ""),
                "ServiceSentiment": doc.get("ServiceSentiment", "neutral")
            }
            
            for field in [
                "DeliverySentiment", "QualitySentiment",
                "PriceSentiment", "PackagingSentiment", "ServiceSentiment"
            ]:
                sentiment_counts[review_data[field]] += 1

            fetched_reviews.append(review_data)

        summary = generate_summary(sentiment_counts)
        return jsonify({
            "productId": product_id,
            "analyzed_reviews": fetched_reviews,
            "summary": summary
        }), 200

    except Exception as e:
        print(f"Error in fetch_reviews: {e}")
        return jsonify({"error": "An error occurred while fetching reviews"}), 500


def generate_summary(sentiment_counts):
    prompt = f"""
        Based on the following customer feedback statistics:
        - Positive mentions: {sentiment_counts['positive']}
        - Negative mentions: {sentiment_counts['negative']}
        - Neutral mentions: {sentiment_counts['neutral']}

        Please write a concise, natural-sounding summary of the overall sentiment. 
        - If positive mentions are high, highlight the key strengths in a friendly, encouraging tone.
        - If negative mentions are significant, acknowledge the main issue succinctly, and include a gentle, constructive idea for improvement.
        - If there are many neutral mentions, briefly suggest why customers might not be strongly positive or negative, and include a small recommendation to help convert neutral experiences into positive ones.
        - End with a single, practical action or advice that could make the biggest difference going forward.

        Aim to sound helpful and human, but keep it short and impactful—avoid unnecessary detail or deep analysis.

        Finally, return your response as a JSON object in the format:
        {{
            "summary": "Your personalized summary here."
        }}
    """
    result = gpt_request(prompt)
    if isinstance(result, dict):
        return result.get("summary", "Summary generation failed")
    return "Summary generation failed"


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


def gpt_request(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        content = response["choices"][0]["message"]["content"].strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"GPT response is not JSON: {content}")
            return {"error": "Invalid response from AI"}
    except Exception as e:
        print(f"Error in GPT request: {e}")
        return {"error": "Unable to process request"}


if __name__ == '__main__':
    app.run(debug=True, port=5002)
