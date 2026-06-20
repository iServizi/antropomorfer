from google import genai
from google.genai import types
import os
import json
from PIL import Image, ImageDraw, ImageFont
from IPython.display import display

client = genai.Client(
    api_key= os.getenv("GEMINI_API_KEY")
    )

def generate_no_animal_image() -> tuple:
    """
    Generates a "NO ANIMAL ON THE PHOTO" image.

    Parameters:
        No parameters.

    Returns:
        img: Returns "NO ANIMAL ON THE PHOTO" image and operation status.
    """
     
    img = Image.new("RGB", (800, 400), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    text = "NO ANIMAL ON THE PHOTO"
    font_size = 45

    try:
        font = ImageFont.truetype("arial.ttf", size=font_size)
    except IOError:
        font = ImageFont.load_default(size=font_size)
    
    # draw.text((400, 200), text, fill=(255, 255, 255), anchor="mm", font=font)
    # return img

    draw.text((400, 200), text, fill=(255, 255, 255), anchor="mm", font=font)

    llm_status = {
        "status": "success",
        "message": "Fallback image 'NO ANIMAL ON THE PHOTO' was successfully generated and stored."
    }

    return llm_status, img


def detect_animal(image: Image.Image) -> dict:
    """
    Detects whether the photo contains an animal.

    Parameters:
        image (Image.Image): A PIL Image object.

    Returns:
        dict: Detection result indicating whether an animal was detected,
        the type of animal (if any), and an optionally generated image.
    """

    response = client.models.generate_content(
    model= "gemini-flash-lite-latest", # "gemini-2.5-flash-lite" , "gemini-2.5-flash"
    contents=[
        image,
        """Is there an animal in the picture?
        Return exclusively JSON:
        {"detected": true/false,
         "animal": "name of the animal or null"}"""
    ],
    config=types.GenerateContentConfig(
        response_mime_type="application/json"
        )
    )

    if not response.text:
        return {"detected": False, "animal": None, "error": "Empty response from API"}

    return json.loads(response.text)


tools = [
    {
        "type": "function",
        "name": "detect_animal",
        "description": "Detects whether there is an animal in the currently uploaded photo.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "generate_no_animal_image",
        "description": "Generates an image displaying the message 'NO ANIMAL ON THE PHOTO' when no animal is detected in the input image.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        },
        "strict": True
    }
]
