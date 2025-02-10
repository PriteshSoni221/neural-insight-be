from transformers import GPT2Tokenizer, GPT2LMHeadModel, Trainer, TrainingArguments, DataCollatorForLanguageModeling
from datasets import Dataset
import json
import torch


def load_data(json_paths):
    data = []
    for json_path in json_paths:
        with open(json_path, "r") as file:
            data.extend(json.load(file))
    return data


def preprocess_data(data):
    formatted_data = []
    for entry in data:
        input_text = entry["input"]
        output_text = "\n".join(
            [
                f"{aspect}: {details['sentiment']}, text: {details['text']}"
                for aspect, details in entry["output"].items()
            ]
        )
        formatted_data.append(f"Input: {input_text}\nOutput:\n{output_text}\n")
    return formatted_data


def prepare_dataset(formatted_data):
    return Dataset.from_dict({"text": formatted_data})


model_name = "gpt2"
tokenizer = GPT2Tokenizer.from_pretrained(model_name)
model = GPT2LMHeadModel.from_pretrained(model_name)


if tokenizer.pad_token is None:
    tokenizer.add_special_tokens({'pad_token': '[PAD]'})
    model.resize_token_embeddings(len(tokenizer))


json_paths = [
    "E:\seiminar\DS2\Sentiment Analysis\JayenGUO2024\model_test/combined_reviews.json"
    "/mnt/data/new_training_data.json"
]
data = load_data(json_paths)

formatted_data = preprocess_data(data)
dataset = prepare_dataset(formatted_data)


def tokenize_function(examples):
    return tokenizer(examples["text"], truncation=True, padding="max_length", max_length=512)

tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["text"])


train_size = int(0.9 * len(tokenized_dataset))
train_dataset = tokenized_dataset.select(range(train_size))
eval_dataset = tokenized_dataset.select(range(train_size, len(tokenized_dataset)))

# Data collator
data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,
)


training_args = TrainingArguments(
    output_dir="./gpt2-finetuned",
    evaluation_strategy="steps",
    eval_steps=500,
    learning_rate=5e-5,
    weight_decay=0.01,
    num_train_epochs=5,
    per_device_train_batch_size=8,
    save_steps=500,
    save_total_limit=3,
    logging_dir="./logs",
    logging_steps=100,
    warmup_steps=200,
    fp16=torch.cuda.is_available(),
)


trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    tokenizer=tokenizer,
    data_collator=data_collator,
)


trainer.train()


trainer.save_model("./gpt2-finetuned")
tokenizer.save_pretrained("./gpt2-finetuned")
