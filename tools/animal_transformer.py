import os
import io
import httpx
import base64
import requests
from PIL import Image
from openai import OpenAI

def save_image_from_response(response) -> Image.Image:
    """
    Extracts image data from the OpenAI response object (either base64 or URL)
    and returns a fully realized PIL Image object.

    Parameters:
        response: Transformed image response from the model.

    Returns:
        Image
    """
    item = response.data[0]
    if getattr(item, "b64_json", None):
        image_data = base64.b64decode(item.b64_json)
    elif getattr(item, "url", None):
        image_data = requests.get(item.url).content
    else:
        raise ValueError("Missing image data inside the API response structure.")
    
    return Image.open(io.BytesIO(image_data))


def transform_animal_to_human(sex: str, image: Image.Image) -> Image.Image:
    """
    Directly executes the gpt-image-1 API edit call with the master prompt rules.
    Downloads the resulting generation and returns a live PIL Image object and operation status.

    Parameters:
            sex: Sex parameter for the transformation.
            image: Image to be transformed.
    Returns:
        Transformaiton status and transformed image.
    """
    api_key = os.getenv("OPENAI_API_KEY") 
    if not api_key:
        raise ValueError("CRITICAL: OPENAI_API_KEY environment variable is missing!")

    client = OpenAI(
        api_key=api_key,
        timeout=httpx.Timeout(120.0, connect=10.0),
    )
    
    if image.size != (1024, 1024):
        image = image.resize((1024, 1024), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    full_prompt = f"""You are a highly skilled cinematic portrait artist and visual transformation expert.

Your task is to analyze the uploaded image and transform the real animal (dog, cat, rabbit, horse, bird, etc.) into a human.

Follow these instructions EXACTLY:

1. Human Transformation
   - Replace ONLY the animal with a realistic human {sex} portrait representing what this animal would look like as a person.
   - Preserve the original pose, camera angle, framing, lighting direction, mood, and perspective.
   - Keep the background and surroundings EXACTLY identical to the source image.
   - Do not alter objects, furniture, scenery, shadows, or composition outside the animal itself.

2. Appearance Mapping Rules
   Carefully translate the animal's physical traits into believable human characteristics:
   - Fur color → skin tone, hair color, eyebrows, eyelashes
   - Eye color → human eye color
   - Fur texture/pattern → hairstyle, freckles, skin texture, makeup accents, facial features, clothing details
   - Animal personality and expression → human facial expression and vibe
   - Animal age → estimated human age
   - Animal breed/species characteristics → facial structure, ethnicity cues, body language, fashion style

3. Color Translation Logic
   - If the animal has predominantly very dark or black fur:
     Generate very deep rich skin tones inspired by the animal coloration.
     Use dark eyes and matching facial features. Preserve elegance and realism.
   - If the animal has predominantly white fur:
     Incorporate realistic albinism traits: pale skin, white/platinum hair,
     very light eyebrows/lashes, pale blue, gray, pinkish, or light hazel eyes.
     Maintain a natural, beautiful, high-fashion appearance.
   - If the animal has mixed or patterned fur:
     Reflect those patterns subtly in hair highlights, freckles,
     heterochromia, skin undertones, makeup, or clothing accents.

4. Human Personality & Style
   The human {sex} should appear: charming, friendly, approachable, relaxed,
   socially confident, stylish and expressive.
   The result should feel believable, emotionally warm, and visually premium.

5. Image Style
   - Hyper-realistic photography
   - Cinematic portrait lighting
   - Natural skin texture
   - Professional DSLR quality
   - Ultra-detailed eyes
   - High dynamic range
   - Photorealistic color grading
   - Authentic human proportions
   - No cartoon, anime, CGI, or exaggerated fantasy elements unless strongly implied by the source image.

6. Critical Constraints
   - Keep the exact original background.
   - Preserve original image composition.
   - Replace ONLY the animal.
   - The final person must clearly feel like the human incarnation of that specific animal.
   - Avoid generic humans.
   - Focus heavily on translating the animal's identity, mood, and coloration into human form."""

    # Triggering image modifications via your gpt-image-1 model
    response = client.images.edit(
        model="gpt-image-1",
        image=("image.png", image_bytes, "image/png"),
        prompt=full_prompt,
        n=1,
        size="1024x1024",
    )

    transform_img = save_image_from_response(response)
    llm_status = {
        "status": "success",
        "message": "Transformaiton img created."
        }

    return llm_status, transform_img

tools = [
    {
        "type": "function",
        "name": "transform_animal_to_human",
        "description": "Transforms the verified animal in the active image into its cinematic human character avatar counterpart. Requires the target gender parameter.",
        "parameters": {
            "type": "object",
            "properties": {
                "sex": {
                    "type": "string",
                    "description": "The requested gender profile mapping for the target human output character, e.g., 'male', 'female', 'man', 'woman'."
                }
            },
            "required": ["sex"],
            "additionalProperties": False
        },
        "strict": True
    }
]