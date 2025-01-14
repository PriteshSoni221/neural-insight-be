import spacy

# Load spaCy's English model
#nlp = spacy.load("en_core_web_sm")
nlp = spacy.load(R'C:\Users\Hp\AppData\Local\Programs\Python\Python311\Lib\site-packages\en_core_web_sm\en_core_web_sm-3.8.0')

def custom_split_sentences(paragraph):
    # Use spaCy to parse the paragraph
    doc = nlp(paragraph)
    sentences = []
    temp_sentence = ""

    for token in doc:
        temp_sentence += token.text_with_ws

        # If the token is a sentence connector or a conjunction
        if token.text.lower() in {
            "and", "but", "or", "nor", "for", "so", "yet",  # Coordinating conjunctions
            "although", "because", "since", "unless", "while", "whereas", "though", "if", "as", "than",
            # Subordinating conjunctions
            "however", "therefore", "nevertheless", "moreover", "furthermore", "consequently", "otherwise"
            # Conjunctive adverbs
        }:
            sentences.append(temp_sentence.strip())
            temp_sentence = ""
        # Break sentences at punctuation or when capitalization indicates a new sentence
        elif token.is_punct or (token.is_space and token.nbor(1).is_title):
            sentences.append(temp_sentence.strip())
            temp_sentence = ""

    # Append the remaining sentence
    if temp_sentence.strip():
        sentences.append(temp_sentence.strip())

    return sentences


# Example usage
paragraph = "I love the product. It is the last longing. The delivery was slow though. It took more than I expected. However, it is pretty good for the price."
sentences = custom_split_sentences(paragraph)
print(sentences)
