from flask import Flask, request, jsonify
from pymongo import MongoClient
import openai
import os
from dotenv import load_dotenv

load_dotenv() 

app = Flask(__name__)


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

# Upload reviews and perform sentiment analysis
@app.route('/upload_reviews', methods=['POST'])
def upload_reviews():
    try:
        data = request.json
        product_id = data.get("product_id")
        reviews = data.get("reviews")

        if not product_id or not reviews:
            return jsonify({"error": "Product ID and reviews are required"}), 400

        analyzed_reviews = []
        for review in reviews:
            review_text = review.get("text")
            if review_text:
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

        return jsonify({"product_id": product_id, "analyzed_reviews": analyzed_reviews}), 200

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
        refined_result = refine_analysis(review_text, correction_prompt, history)

        if refined_result:
            history.append({"correction_type": correction_type, "output": refined_result})
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

#  sentiment analysis
def analyze_sentiment(review_text):
    prompt = f"""
        You are an assistant that extracts sentiments for reviews. Break the input into the categories:
        delivery, quality, price, packaging, and service.
        For each category, provide:
        - The text related to the category.
        - The sentiment (positive, negative, or neutral).
        Respond in JSON format only.
        Input: "{review_text}"
        Output:
    """
    return gpt_request(prompt)

#  using predefined correction prompts
def refine_analysis(review_text, correction_type, history):
    """
    Automatically refines sentiment analysis based on predefined correction options.
    - Retrieves predefined correction prompt based on user selection.
    - Automatically builds history of previous corrections.
    """


    correction_prompt = CORRECTION_OPTIONS.get(correction_type, "Ensure the analysis is accurate.")


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


# this is for openai
def gpt_request(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        result = response["choices"][0]["message"]["content"]
        return eval(result)  # Convert JSON string to dictionary
    except Exception as e:
        print(f"Error in GPT request: {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True, port=5000)
