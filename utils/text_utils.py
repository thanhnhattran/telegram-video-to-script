def split_text(text: str, max_length: int = 4000) -> list[str]:
    """Split text into chunks respecting paragraph boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current = ""

    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_length:
            if current:
                chunks.append(current.strip())
                current = ""
            # Handle single paragraph longer than max_length
            if len(paragraph) > max_length:
                for line in paragraph.split("\n"):
                    if len(current) + len(line) + 1 > max_length:
                        if current:
                            chunks.append(current.strip())
                        current = line + "\n"
                    else:
                        current += line + "\n"
            else:
                current = paragraph + "\n\n"
        else:
            current += paragraph + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks
