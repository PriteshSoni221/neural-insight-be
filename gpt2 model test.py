
from transformers import GPT2LMHeadModel, GPT2Tokenizer


test_input = "Sehr schnelle Lieferung. Toller Rechner, sieht nicht nur top aus, sondern ist bestens vorinstalliert und super fix in allem. Ganz besonders toll fand ich die persönlichen Nachrichten und die Aufmerksamkeiten. Rechner läuft seit drei Tagen stabil, bin begeistert!"


model_path = "E:/seiminar/DS2/Sentiment Analysis/JayenGUO2024/model_test/gpt2-finetuned"
tokenizer = GPT2Tokenizer.from_pretrained(model_path)
model = GPT2LMHeadModel.from_pretrained(model_path)


input_text = f"Input: {test_input}\nOutput:"
input_ids = tokenizer(test_input, return_tensors="pt").input_ids


output_ids = model.generate(
    input_ids,
    max_length=100,
    num_beams=5,
    early_stopping=True,
    pad_token_id=tokenizer.pad_token_id,
)

generated_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
print("Generated Output:")
print(generated_text)
