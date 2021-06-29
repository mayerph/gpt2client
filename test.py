from gpt2_client import GPT2Client

gpt2 = GPT2Client('124M')  # This could also be `355M`, `774M`, or `1558M`
gpt2.load_model()

prompts = [
    "",
]

# returns an array of generated text
text = gpt2.generate(n_samples=1, return_text=True, words=40)

print("-", text, "-")
