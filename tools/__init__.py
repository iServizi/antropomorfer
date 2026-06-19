from .image_tools import detect_animal, generate_no_animal_image, tools as img_tools
from .animal_transformer import transform_animal_to_human, tools as transform_tools
all_tools = img_tools + transform_tools