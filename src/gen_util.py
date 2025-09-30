import os
import time
import requests
import aiohttp
import asyncio
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import re
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm, colors


def mask_sensitive_words(
    sentence,
    target_words,
    reverse_ascii=False,
    partial_ascii=False,
    random_ascii=False,
    mask_from_start=False,
    ratio=0.5,
):
    def word_to_partial_ascii(word, ratio=ratio, mask_from_start=mask_from_start):
        """Convert a percentage of a word's characters to ASCII."""
        length_to_mask = int(len(word) * ratio)
        if mask_from_start:
            # Mask the first 'length_to_mask' characters
            ascii_indices = range(0, length_to_mask)
        else:
            # Mask the last 'length_to_mask' characters
            ascii_indices = range(len(word) - length_to_mask, len(word))

        masked = ""
        for i, char in enumerate(word):
            if i not in ascii_indices:
                masked += char
            elif i == ascii_indices[0]:
                masked += "[" + str(ord(char))
            elif i == ascii_indices[-1]:
                masked += " " + str(ord(char)) + "]"
            else:
                masked += " " + str(ord(char))
        return masked

    def word_to_random_ascii(word, ratio):
        """Randomly convert a percentage of a word's characters to ASCII."""
        num_chars_to_mask = int(len(word) * ratio)
        ascii_indices = random.sample(range(len(word)), num_chars_to_mask)

        masked = ""
        for i, char in enumerate(word):
            if i not in ascii_indices:
                masked += char
            else:
                masked += "[" + str(ord(char)) + "]"
        return masked

    def word_to_ascii(word):
        """Convert the entire word to ASCII."""
        ascii_codes = [ord(char) for char in word]
        if reverse_ascii:
            ascii_codes.reverse()
        return "[" + " ".join(str(code) for code in ascii_codes) + "]"

    # Split sentence into words, including dash-separated words and punctuation
    words = re.findall(r"[\w-]+|\s+|[^\w\s]", sentence)
    result = []

    for word in words:
        clean_word = "".join(
            e for e in word if e.isalnum() or e == "-"
        )  # Keep alphanumeric and dashes
        modified_word = word
        for target in target_words:
            # Check if target is a substring (case-insensitive)
            start_idx = clean_word.lower().find(target.lower())
            if start_idx != -1:
                if random_ascii:
                    target_masked = word_to_random_ascii(
                        clean_word[start_idx : start_idx + len(target)], ratio=ratio
                    )
                elif partial_ascii:
                    target_masked = word_to_partial_ascii(
                        clean_word[start_idx : start_idx + len(target)], ratio=ratio
                    )
                else:
                    target_masked = word_to_ascii(
                        clean_word[start_idx : start_idx + len(target)]
                    )
                # Replace only the matched part of the word
                modified_word = (
                    modified_word[:start_idx]
                    + target_masked
                    + modified_word[start_idx + len(target) :]
                )
        result.append(modified_word)

    # Reconstruct sentence with proper spacing
    output = "".join(result)

    return output


class LanguageModel:
    def __init__(self, model):
        """
        Initialize the appropriate client for the given model.

        Parameters
        ----------
        model : str
            The model name to determine which client to use (e.g., OpenAI, Anthropic, or Hugging Face).
        """
        if "gpt" in model:
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key:
                raise ValueError(
                    "🚨 Oops! The 'OPENAI_API_KEY' environment variable is not set."
                )
            self.model = OpenAIClient(model, api_key=openai_key)
            print("✨ OpenAI GPT model has been initialized successfully!")

        elif "claude" in model:
            anthropic_key = os.getenv("ANTHROPIC_API_KEY")
            if not anthropic_key:
                raise ValueError(
                    "🚨 Oops! The 'ANTHROPIC_API_KEY' environment variable is not set."
                )
            self.model = AnthropicClient(model, api_key=anthropic_key)
            print("✨ Anthropic Claude model has been initialized successfully!")

        else:
            # Assume it's a Hugging Face model if not OpenAI or Anthropic
            self.model = HFModel(model)
            print(f"✨ Hugging Face {model} has been initialized successfully!")

        print("🎉 Your Language Model is ready to use!")


class HFModel:
    def __init__(self, model):
        self.tokenizer = AutoTokenizer.from_pretrained(
            model, token=os.environ["HF_TOKEN"]
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            token=os.environ["HF_TOKEN"],
        )

    def complete(
        self,
        prompt,
        max_length,
        do_sample,
        temperature,
        history=None,
        pad_token_id=None,
        silent=False,
        instruction=None,
        num_beams=1,
        inspect_topk=None,  # Add inspect_topk argument
    ):
        """
        Generate a completion using a Hugging Face Transformer model.

        Parameters
        ----------
        prompt : str
            The user input or query to serve as the base for text generation.
        max_length : int
            The maximum length of the generated output sequence.
        do_sample : bool
            Whether to use sampling during text generation.
        temperature : float
            Sampling temperature. Higher values produce more randomness.
        inspect_topk : int, optional
            If provided, returns the top-k tokens and their probabilities at the last token.
        history : list, optional
            Conversation history to maintain context. Defaults to None.
        silent : bool, optional
            If True, suppresses printing the input prompt.

        Returns
        -------
        response : str or dict
            The generated text response from the model. If `inspect_topk` is set,
            it also includes top-k token probabilities.
        history : list
            Updated conversation history including the new user-assistant exchange.
        """
        if instruction:
            prompt = f"{instruction}\n {prompt}"

        if history is None:
            history = []

        user_prompt = [{"role": "user", "content": prompt}]
        dialogue = history + user_prompt

        formatted_prompt = self.tokenizer.apply_chat_template(
            dialogue, tokenize=False, add_generation_prompt=True
        )

        if not silent:
            print(f"🎅: {prompt}")

        # Tokenize and prepare for generation
        input_ids = self.tokenizer(formatted_prompt, return_tensors="pt").to("cuda")
        outputs = self.model.generate(
            input_ids=input_ids.input_ids,
            attention_mask=input_ids.attention_mask,
            max_length=max_length,
            do_sample=do_sample,
            temperature=temperature,
            pad_token_id=pad_token_id,
            num_beams=num_beams,
            early_stopping=num_beams > 1,
            num_return_sequences=num_beams,
            return_dict_in_generate=bool(inspect_topk),
            output_scores=bool(inspect_topk),
        )
        if inspect_topk:
            outputs, logits = outputs.sequences, outputs.scores

        # Decode outputs
        if num_beams > 1:
            response = []
            for i in range(num_beams):
                r = self.tokenizer.decode(
                    outputs[i, len(input_ids.input_ids[0]) :], skip_special_tokens=True
                )
                response.append(r)
        else:
            # Decode the generated response
            generated_token_ids = outputs[
                0, len(input_ids.input_ids[0]) :
            ]  # Get generated token IDs
            response = self.tokenizer.decode(
                generated_token_ids, skip_special_tokens=True
            )  # Decode response

            # Store the generated tokens for further use
            if inspect_topk:
                generated_tokens = [
                    self.tokenizer.decode([token_id], skip_special_tokens=False)
                    for token_id in generated_token_ids
                ]

        # Inspect top-k tokens and probabilities
        all_topk_info = []  # List to store top-k information for each token
        if inspect_topk:
            # Iterate over each token's logits
            for token_position, position_logits in enumerate(logits):
                # Compute top-k indices and probabilities for the current token
                topk = torch.topk(position_logits[0], inspect_topk)
                topk_indices = topk.indices
                topk_logprobs = torch.log_softmax(position_logits[0], dim=-1)[
                    topk_indices
                ]
                # Decode top-k tokens and their probabilities for the current token
                topk_info = [
                    {
                        "token": self.tokenizer.decode([token_id]),
                        "logprob": prob.item(),
                    }
                    for token_id, prob in zip(topk_indices, topk_logprobs)
                ]

                # Append the result with token position for better traceability
                all_topk_info.append(
                    {
                        "token": generated_tokens[token_position],
                        "top_logprobs": topk_info,
                    }
                )
        # Update conversation history
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": response})

        # Return response with top-k inspection if applicable
        if inspect_topk:
            return {"response": response, "topk_tokens": all_topk_info}, history
        else:
            return response, history

    def multi_turn_conversation(self, max_length, do_sample, temperature):
        """
        Run a multi-turn conversation loop with the Hugging Face model.

        Parameters
        ----------
        max_length : int
            The maximum length of the generated output sequence.
        do_sample : bool
            Whether to use sampling during text generation.
        temperature : float
            Sampling temperature. Higher values produce more randomness.
        """

        conversation_history = []

        while True:
            # Get user input
            user_input = input("User: ").strip()

            if user_input.lower() == "exit":
                print("Ending the conversation.")
                break

            # Call complete method for a model-generated response
            model_reply, conversation_history = self.complete(
                user_input,
                max_length=max_length,
                do_sample=do_sample,
                temperature=temperature,
                history=conversation_history,
            )

            # Print the assistant's reply
            print(f"🤖: {model_reply}")

        return conversation_history


class OpenAIClient:
    def __init__(self, model, api_key=None):
        """
        Initialize the OpenAI client.
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required.")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.model = model

    def prepare_request_data(
        self,
        prompt,
        max_tokens,
        temperature,
        logprobs=False,
        top_logprobs=None,
        echo=False,
        n=1,
        instruction=None,
    ):
        """
        Prepare request data for OpenAI API based on the model type.

        Parameters
        ----------
        prompt : str
            The input prompt for the model.
        max_tokens : int
            Maximum number of tokens to generate.
        temperature : float
            Sampling temperature. Higher values produce more randomness.
        logprobs : bool, optional
            Whether to return log probabilities of the output tokens.
        top_logprobs : int or None, optional
            Number of most likely tokens to return at each token position with their log probabilities.
            Requires logprobs to be set to True.
        echo : bool, optional
            Whether to include the prompt in the response.
        n : int, optional
            Number of completions to generate.
        instruction : str, optional
            System instruction for chat-based models.

        Returns
        -------
        tuple
            The API URL and the prepared request data.
        """
        # Validate `top_logprobs` usage
        if top_logprobs is not None:
            if not logprobs:
                raise ValueError(
                    "`logprobs` must be set to True when using `top_logprobs`."
                )
            if not (0 <= top_logprobs <= 20):
                raise ValueError("`top_logprobs` must be an integer between 0 and 20.")

        if "turbo" in self.model or "4o" in self.model or "chat" in self.model:
            # Use chat completion endpoint for chat-based models
            api_url = "https://api.openai.com/v1/chat/completions"

            # Construct messages format for chat models
            messages = [{"role": "user", "content": prompt}]
            if instruction:
                messages.insert(0, {"role": "system", "content": instruction})

            # Prepare the request payload
            data = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "n": n,
            }

            # Add logprobs and top_logprobs if logprobs is enabled
            if logprobs:
                data["logprobs"] = True
                if top_logprobs is not None:
                    data["top_logprobs"] = top_logprobs

        else:
            # Use completion endpoint for standard models
            api_url = "https://api.openai.com/v1/completions"

            # Include instruction if provided
            if instruction:
                prompt = instruction + "\n" + prompt

            # Prepare the request payload
            data = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "logprobs": logprobs,  # Include logprobs
                "echo": echo,
                "n": n,
            }

            # Add top_logprobs if logprobs is enabled and top_logprobs is provided
            if logprobs and top_logprobs is not None:
                data["top_logprobs"] = top_logprobs

        return api_url, data

    async def complete_async(
        self,
        prompt,
        max_tokens,
        temperature,
        logprobs=None,
        echo=False,
        n=None,
        instruction=None,
    ):
        """
        Asynchronous method to interact with the OpenAI API.
        """
        api_url, data = self.prepare_request_data(
            prompt, max_tokens, temperature, logprobs, echo, n, instruction
        )

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.post(
                        api_url, headers=self.headers, json=data
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            if "turbo" in self.model or "4o" in self.model:
                                return result["choices"][0]["message"]["content"]
                            else:
                                return result["choices"][0]["text"]
                        else:
                            print(f"Error {response.status}: {await response.text()}")
                            await asyncio.sleep(1)
                except Exception as e:
                    print("API error:", e)
                    await asyncio.sleep(1)

    def complete(
        self,
        prompt,
        max_tokens,
        temperature,
        logprobs=None,
        echo=False,
        n=1,
        instruction=None,
        history=None,
        silent=False,
        inspect_topk=None,
    ):
        """
        Synchronous method to interact with the OpenAI API.
        """

        api_url, data = self.prepare_request_data(
            prompt,
            max_tokens,
            temperature,
            True if inspect_topk else False,
            inspect_topk,
            echo,
            n,
            instruction,
        )

        if history is None:
            history = []

        # Add user input to the conversation history
        history.append({"role": "user", "content": prompt})

        if not silent:
            print(f"🎅: {prompt}")
        max_try, count = 5, 0
        while count <= max_try:
            try:
                response = requests.post(api_url, headers=self.headers, json=data)
                if response.status_code == 200:
                    result = response.json()
                    if "turbo" in self.model or "4o" or "chat" in self.model:
                        model_reply = result["choices"][0]["message"]["content"]
                    else:
                        model_reply = result["choices"][0]["text"]

                    history.append({"role": "assistant", "content": model_reply})

                    # Extract top-k tokens if inspect_topk is enabled
                    if inspect_topk:
                        logprobs_info = result["choices"][0].get("logprobs", {})

                        # Return the response and top-k tokens
                        return {
                            "response": model_reply,
                            "topk_tokens": logprobs_info,
                        }, history

                    return model_reply, history
                else:
                    print(f"Error {response.status_code}: {response.text}")
                    count += 1
                    time.sleep(1)
            except Exception as e:
                print("API error:", e)
                count += 1
                time.sleep(1)

    def multi_turn_conversation(
        self, max_tokens, temperature, instruction=None, async_mode=False
    ):
        """
        Multi-turn conversation loop with OpenAI API.
        """
        history = [{"role": "system", "content": instruction}] if instruction else []

        while True:
            user_input = input("User: ").strip()
            if user_input.lower() == "exit":
                print("Ending the conversation.")
                break

            if async_mode:
                response = asyncio.run(
                    self.complete_async(
                        prompt=user_input,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        instruction=instruction,
                        history=history,
                    )
                )
            else:
                response, history = self.complete(
                    prompt=user_input,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    instruction=instruction,
                    history=history,
                )

            print(f"🤖: {response}")

        return history


class AnthropicClient:
    def __init__(self, model, api_key=None):
        """
        Initialize the Anthropic client with the provided API key or environment variable.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required.")
        self.headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        self.model = model

    def complete(
        self,
        prompt,
        max_tokens,
        temperature,
        stop_sequences=None,
        instruction=None,
        conversation_history=None,
        silent=False,
    ):
        """
        Synchronous request to the Anthropic API for text generation.

        Parameters
        ----------
        prompt : str
            User input for text generation.
        max_tokens : int
            Maximum tokens for the response.
        temperature : float
            Sampling temperature.
        model_name : str
            Name of the Anthropic model.
        stop_sequences : list or None
            Optional list of stop sequences.
        instruction : str or None
            Instruction or system prompt for context.
        conversation_history : list or None
            List of previous messages for context.
        silent : bool
            If True, suppresses user input display.

        Returns
        -------
        response : str
            Generated text response.
        conversation_history : list
            Updated conversation history.
        """
        # Initialize conversation history if not provided
        if conversation_history is None:
            conversation_history = []

        # Add user input to the conversation history
        conversation_history.append({"role": "user", "content": prompt})

        # Prepare data payload
        data = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": conversation_history,
            "temperature": temperature,
        }

        # Add optional stop sequences
        if stop_sequences:
            data["stop_sequences"] = stop_sequences

        # Print user input if not silent
        if not silent:
            print(f"🎅: {prompt}")

        # API request loop
        while True:
            try:
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=self.headers,
                    json=data,
                )
                if response.status_code == 200:
                    result = response.json()
                    model_reply = result["content"][0]["text"]

                    # Add assistant response to conversation history
                    conversation_history.append(
                        {"role": "assistant", "content": model_reply}
                    )

                    return model_reply, conversation_history
                else:
                    print(f"Error {response.status_code}: {response.text}")
                    time.sleep(1)
            except Exception as error:
                print("API error:", error)
                time.sleep(1)

    def multi_turn_conversation(
        self, max_tokens, temperature, stop_sequences=None, instruction=None
    ):
        """
        Multi-turn conversation loop with the Anthropic API.

        Parameters
        ----------
        max_tokens : int
            Maximum tokens for the response.
        temperature : float
            Sampling temperature.
        model_name : str
            Name of the Anthropic model.
        stop_sequences : list or None
            Optional list of stop sequences.
        instruction : str or None
            Instruction or system prompt for context.
        """
        conversation_history = []

        while True:
            user_input = input("User: ").strip()

            if user_input.lower() == "exit":
                print("Ending the conversation.")
                break

            # Get model reply via synchronous completion
            model_reply, conversation_history = self.complete(
                prompt=user_input,
                max_tokens=max_tokens,
                temperature=temperature,
                stop_sequences=stop_sequences,
                instruction=instruction,
                conversation_history=conversation_history,
            )
            print(f"🤖: {model_reply}")

        return conversation_history
