from flask import Flask, logging, request, jsonify
from pymongo import MongoClient
import openai
import os
from dotenv import load_dotenv
from flask_cors import CORS, cross_origin

load_dotenv()

app = Flask(__name__)
CORS(app)
cors = CORS(app, resources={r"/*": {"origins": "http://localhost:4200"}})

# logging.getLogger('flask_cors').level = logging.DEBUG

MONGO_URI = os.getenv('MONGO_CONNECTION_STRING')
client = MongoClient(MONGO_URI)


customer_db = client["customer_db"]
user_review_collection = customer_db["user_review"]


openai.api_key = os.getenv('MY_KEY')

#  Predefined correction prompts
CORRECTION_OPTIONS = {
    "missing_quality": "Ensure that the analysis includes a quality-related sentiment if applicable. If there is no mention of quality, confirm that 'neutral' is correct.",
    "missing_delivery": "If the review discusses delivery, ensure it is categorized correctly and labeled with the appropriate sentiment.",
    "missing_price": "If the review mentions anything about price, discounts, value-for-money, or affordability, ensure it is categorized correctly.",
    "missing_packaging": "If the review includes comments about the product's packaging, condition upon arrival, or unboxing experience, ensure it is categorized correctly.",
    "missing_service": "Ensure customer service interactions (e.g., support, responses, instructions) are categorized under 'service' with the appropriate sentiment.",
    "incorrect_sentiment": "Re-evaluate the sentiment scoring and ensure it accurately reflects the tone and context of the review.",
    "missing_category": "Double-check if any other relevant category (quality, price, service, delivery, packaging) is missing and update accordingly.",
    "unclear_analysis": "Ensure the sentiment analysis provides clear and specific information for each category where relevant.",
    "misclassified_text": "Some parts of the review might be misclassified under the wrong category. Ensure each phrase is correctly categorized.",
    "text_not_extracted": "If the sentiment analysis result leaves a category empty but relevant text exists, extract and classify that text appropriately.",
    "too_general": "Ensure the sentiment analysis includes more detailed insights about the review, rather than general statements.",
    "neutral_sentiment_check": "If a category is marked as 'neutral', confirm whether it is truly neutral or if a more accurate sentiment should be assigned.",
    "positive_but_negative_context": "Ensure that if a review contains a positive phrase followed by a negative statement, both are properly analyzed instead of one being ignored.",
    "more_context_needed": "Expand the analysis by taking into account the full review, ensuring that nuances or implications are included."
}


@app.route('/')
def home():
    return "Hey!"


@app.route('/summarize', methods=['POST'])
@cross_origin()
def summarize():
    try:
        data = request.json
        review = data.get("review")
        return jsonify({
            "input": "The item arrived before I expected, but unfortunately the manual wasn't included in the box.",
            "output": {
                "delivery": {
                    "sentiment": "positive",
                    "text": "The item arrived before I expected"
                },
                "packaging": {
                    "sentiment": "negative",
                    "text": "the manual wasn't included in the box"
                },
                "price": {
                    "sentiment": "neutral",
                    "text": ""
                },
                "quality": {
                    "sentiment": "negative",
                    "text": "unfortunately the manual wasn't included in the box"
                },
                "service": {
                    "sentiment": "neutral",
                    "text": ""
                }
            }
        }), 200

    except Exception as e:
        print(f"Error in upload_reviews: {e}")
        return jsonify({"error": "An error occurred while processing reviews"}), 500

# Upload reviews and perform sentiment analysis


@app.route('/upload-reviews', methods=['POST'])
@cross_origin()
def upload_reviews():
    try:
        data = request.json
        product_id = data.get("productID")
        reviews = data.get("fileContent", {}).get("reviews", [])
        is_dummy = data.get("isDummy")

        if is_dummy:
            analyzed_reviews = [
                {
                    "_id": "679bb4aa1b46d8cf42230454",
                    "history": [],
                    "input": "The item arrived before I expected, but unfortunately the manual wasn't included in the box.",
                    "output": {
                        "delivery": {
                            "sentiment": "positive",
                            "text": "The item arrived before I expected"
                        },
                        "packaging": {
                            "sentiment": "negative",
                            "text": "the manual wasn't included in the box"
                        },
                        "price": {
                            "sentiment": "neutral",
                            "text": ""
                        },
                        "quality": {
                            "sentiment": "negative",
                            "text": "unfortunately the manual wasn't included in the box"
                        },
                        "service": {
                            "sentiment": "neutral",
                            "text": ""
                        }
                    }
                }
            ]
            dummy_summary = "Customers appreciate the product's features and usability, but some report issues with customer service. The high number of neutral mentions suggests that many customers are satisfied but not particularly impressed or disappointed. Improving customer service may shift more neutral buyers to a positive experience."
            return jsonify({"productID": product_id, "analyzed_reviews": analyzed_reviews, "summary": dummy_summary}), 200

        if not product_id or not reviews:
            return jsonify({"error": "Product ID and reviews are required"}), 400

        analyzed_reviews = []
        for review_text in reviews:
            sentiment_result = analyze_sentiment(review_text)
            if sentiment_result:
                analysis_result = {
                    "input": review_text,
                    "output": sentiment_result,
                    "history": []
                }
                analyzed_reviews.append(analysis_result)

                # Save to MongoDB
                inserted_review = user_review_collection.insert_one({
                    "product_id": product_id,
                    "review": analysis_result
                })

                # Add MongoDB's `_id` for reference
                analysis_result["_id"] = str(inserted_review.inserted_id)
            else:
                return jsonify({"error": "Sentiment analysis failed"}), 500

        return jsonify({"productID": product_id, "analyzed_reviews": analyzed_reviews}), 200

    except Exception as e:
        print(f"Error in upload_reviews: {e}")
        return jsonify({"error": "An error occurred while processing reviews"}), 500
#  correct sentiment analysis using predefined options


@app.route('/correct_analysis', methods=['POST'])
def correct_analysis():
    try:
        data = request.json
        review_id = data.get("review_id")
        correction_type = data.get("correction_type")

        if not review_id or correction_type not in CORRECTION_OPTIONS:
            return jsonify({"error": "Invalid review ID or correction type"}), 400

        review = user_review_collection.find_one({"_id": review_id})
        if not review:
            return jsonify({"error": "Review not found"}), 404

        review_text = review["review"]["input"]
        previous_output = review["review"]["output"]
        history = review["review"].get("history", [])

        # Use predefined correction prompt
        correction_prompt = CORRECTION_OPTIONS[correction_type]
        refined_result = refine_analysis(
            review_text, correction_prompt, history)

        if refined_result:
            history.append({"correction_type": correction_type,
                           "output": refined_result})
            user_review_collection.update_one(
                {"_id": review_id},
                {"$set": {"review.output": refined_result, "review.history": history}}
            )

            return jsonify({
                "review_id": str(review_id),
                "corrected_output": refined_result,
                "history": history
            }), 200
        else:
            return jsonify({"error": "Failed to refine sentiment analysis"}), 500

    except Exception as e:
        print(f"Error in correct_analysis: {e}")
        return jsonify({"error": "An error occurred while correcting the analysis"}), 500


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
    Respond in JSON format only, without any additional explanation or markdown formatting.
    Input: "{review_text}"
    Output:
    """
    return gpt_request(prompt)


def clean_response(response_text):

    response_text = response_text.strip()
    if response_text.startswith("```") and response_text.endswith("```"):
        response_text = response_text.strip("```")
    return response_text


def refine_analysis(review_text, correction_type, history):
    """
    Automatically refines sentiment analysis based on predefined correction options.
    - Retrieves predefined correction prompt based on user selection.
    - Automatically builds history of previous corrections.
    """

    correction_prompt = CORRECTION_OPTIONS.get(
        correction_type, "Ensure the analysis is accurate.")

    previous_prompts = "\n".join(
        [f"- {CORRECTION_OPTIONS.get(h['correction_type'], 'Previous correction applied.')}" for h in history]
    )

    prompt = f"""
        You are refining sentiment analysis for a customer review.
        The original analysis had issues, and previous refinement attempts were made:
        {previous_prompts}

        Now apply the following correction:
        {correction_prompt}

        Reanalyze the review and provide improved sentiment classification.
        Input: "{review_text}"
        Output:
    """
    return gpt_request(prompt)

# getReviewsByProduct


@app.route('/fetch_reviews', methods=['GET'])
@cross_origin()
def fetch_reviews():
    try:

        product_id_raw = request.args.get("productId")
        if not product_id_raw:
            return jsonify({"error": "Product ID is required"}), 400

        
        try:
            product_id = int(product_id_raw)
        except ValueError:
            return jsonify({"error": "Product ID must be an integer"}), 400
        
        if product_id == 0:
            return {
                "analyzed_reviews": [
                    {
                        "DeliverySentiment": "positive",
                        "DeliveryText": "The item arrived before I expected",
                        "PackagingSentiment": "negative",
                        "PackagingText": "the manual wasn't included in the box",
                        "PriceSentiment": "neutral",
                        "PriceText": "",
                        "Product_id": 34942640,
                        "QualitySentiment": "neutral",
                        "QualityText": "",
                        "ServiceSentiment": "neutral",
                        "ServiceText": "",
                        "Text": "The item arrived before I expected, but unfortunately the manual wasn't included in the box.",
                        "_id": "67955037a049e8ca17d13a7a"
                    },
                    {
                        "DeliverySentiment": "positive",
                        "DeliveryText": "The item arrived before I expected",
                        "PackagingSentiment": "negative",
                        "PackagingText": "the manual wasn't included in the box",
                        "PriceSentiment": "neutral",
                        "PriceText": "",
                        "Product_id": 34942640,
                        "QualitySentiment": "negative",
                        "QualityText": "the manual wasn't included in the box",
                        "ServiceSentiment": "neutral",
                        "ServiceText": "",
                        "Text": "The item arrived before I expected, but unfortunately the manual wasn't included in the box.",
                        "_id": "67a109e796becdb0d490fb9d"
                    },
                    {
                        "DeliverySentiment": "neutral",
                        "DeliveryText": "",
                        "PackagingSentiment": "positive",
                        "PackagingText": "The packaging was secure",
                        "PriceSentiment": "positive",
                        "PriceText": "Great value for the money",
                        "Product_id": 34942640,
                        "QualitySentiment": "positive",
                        "QualityText": "everything works just fine",
                        "ServiceSentiment": "neutral",
                        "ServiceText": "",
                        "Text": "Great value for the money. The packaging was secure, and everything works just fine.",
                        "_id": "67a109ed96becdb0d490fb9e"
                    },
                    {
                        "DeliverySentiment": "positive",
                        "DeliveryText": "Delivery was on time, though.",
                        "PackagingSentiment": "neutral",
                        "PackagingText": "",
                        "PriceSentiment": "negative",
                        "PriceText": "I think it's overpriced",
                        "Product_id": 34942640,
                        "QualitySentiment": "negative",
                        "QualityText": "given the flimsy feeling of the materials.",
                        "ServiceSentiment": "neutral",
                        "ServiceText": "",
                        "Text": "I think it's overpriced, given the flimsy feeling of the materials. Delivery was on time, though.",
                        "_id": "67a109f496becdb0d490fb9f"
                    },
                    {
                        "DeliverySentiment": "neutral",
                        "DeliveryText": "",
                        "PackagingSentiment": "neutral",
                        "PackagingText": "",
                        "PriceSentiment": "neutral",
                        "PriceText": "The product is decent for a budget option.",
                        "Product_id": 34942640,
                        "QualitySentiment": "neutral",
                        "QualityText": "The product is decent for a budget option.",
                        "ServiceSentiment": "positive",
                        "ServiceText": "Customer service was very friendly when I called.",
                        "Text": "Customer service was very friendly when I called. The product is decent for a budget option.",
                        "_id": "67a109f896becdb0d490fba0"
                    },
                    {
                        "DeliverySentiment": "positive",
                        "DeliveryText": "The item arrived before I expected",
                        "PackagingSentiment": "negative",
                        "PackagingText": "unfortunately the manual wasn't included in the box",
                        "PriceSentiment": "neutral",
                        "PriceText": "",
                        "Product_id": 34942640,
                        "QualitySentiment": "negative",
                        "QualityText": "unfortunately the manual wasn't included in the box",
                        "ServiceSentiment": "neutral",
                        "ServiceText": "",
                        "Text": "The item arrived before I expected, but unfortunately the manual wasn't included in the box.",
                        "_id": "67a10c0289f5502b0c8386d6"
                    },
                    {
                        "DeliverySentiment": "positive",
                        "DeliveryText": "The item arrived before I expected",
                        "PackagingSentiment": "negative",
                        "PackagingText": "unfortunately the manual wasn't included in the box",
                        "PriceSentiment": "neutral",
                        "PriceText": "",
                        "Product_id": 34942640,
                        "QualitySentiment": "negative",
                        "QualityText": "unfortunately the manual wasn't included in the box",
                        "ServiceSentiment": "neutral",
                        "ServiceText": "",
                        "Text": "The item arrived before I expected, but unfortunately the manual wasn't included in the box.",
                        "_id": "67a10c6c89f5502b0c8386d7"
                    }
                ],
                "productId": 34942640,
                "summary": "The feedback shows a balanced mix of positive and negative sentiments, with a notably high number of neutral mentions. This suggests that while some customers are satisfied and others have concerns, many are not fully engaged or impacted. To enhance the overall customer experience, consider focusing on increasing the distinctiveness and appeal of your offerings to convert neutral perceptions into positive ones. A good starting point could be to more actively solicit and act on customer feedback to understand and address specific areas of ambiguity or indifference."
            }


        reviews_cursor = user_review_collection.find(
            {"Product_id": product_id})
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
    app.run(debug=True, port=5000)
