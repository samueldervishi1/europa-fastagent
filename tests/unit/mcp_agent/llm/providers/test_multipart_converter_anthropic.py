import base64
import unittest

from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    PromptMessage,
    TextContent,
    TextResourceContents,
)
from pydantic import AnyUrl

from mcp_agent.llm.providers.multipart_converter_anthropic import (
    AnthropicConverter,
)
from mcp_agent.mcp.prompt_message_multipart import PromptMessageMultipart
from mcp_agent.mcp.resource_utils import normalize_uri

PDF_BASE64 = base64.b64encode(b"fake_pdf_data").decode("utf-8")


def create_pdf_resource(pdf_base64) -> EmbeddedResource:
    pdf_resource: BlobResourceContents = BlobResourceContents(
        uri="test://example.com/document.pdf",
        mimeType="application/pdf",
        blob=pdf_base64,
    )
    return EmbeddedResource(type="resource", resource=pdf_resource)


class TestAnthropicUserConverter(unittest.TestCase):
    """Test cases for conversion from user role MCP message types to Anthropic API."""

    def setUp(self):
        """Set up test data."""
        self.sample_text = "This is a test message"
        self.sample_image_base64 = base64.b64encode(b"fake_image_data").decode("utf-8")

    def test_text_content_conversion(self):
        """Test conversion of TextContent to Anthropic text block."""
        # Create a text content message
        text_content = TextContent(type="text", text=self.sample_text)
        multipart = PromptMessageMultipart(role="user", content=[text_content])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - using dictionary access, not attribute access
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], self.sample_text)

    def test_image_content_conversion(self):
        """Test conversion of ImageContent to Anthropic image block."""
        # Create an image content message
        image_content = ImageContent(
            type="image", data=self.sample_image_base64, mimeType="image/jpeg"
        )
        multipart = PromptMessageMultipart(role="user", content=[image_content])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - using dictionary access
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "image")
        self.assertEqual(anthropic_msg["content"][0]["source"]["type"], "base64")
        self.assertEqual(anthropic_msg["content"][0]["source"]["media_type"], "image/jpeg")
        self.assertEqual(anthropic_msg["content"][0]["source"]["data"], self.sample_image_base64)

    def test_embedded_resource_text_conversion(self):
        """Test conversion of text-based EmbeddedResource to Anthropic document block."""
        # Create a text resource
        text_resource = TextResourceContents(
            uri="test://example.com/document.txt",
            mimeType="text/plain",
            text=self.sample_text,
        )
        embedded_resource = EmbeddedResource(type="resource", resource=text_resource)
        multipart = PromptMessageMultipart(role="user", content=[embedded_resource])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - using dictionary access
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "document")
        self.assertEqual(anthropic_msg["content"][0]["source"]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["title"], "document.txt")
        self.assertEqual(anthropic_msg["content"][0]["source"]["media_type"], "text/plain")
        self.assertEqual(anthropic_msg["content"][0]["source"]["data"], self.sample_text)

    def test_embedded_resource_pdf_conversion(self):
        """Test conversion of PDF EmbeddedResource to Anthropic document block."""
        # Create a PDF resource
        pdf_resource = create_pdf_resource(PDF_BASE64)
        multipart = PromptMessageMultipart(role="user", content=[pdf_resource])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - using dictionary access
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "document")
        self.assertEqual(anthropic_msg["content"][0]["source"]["type"], "base64")
        self.assertEqual(anthropic_msg["content"][0]["source"]["media_type"], "application/pdf")
        self.assertEqual(anthropic_msg["content"][0]["source"]["data"], PDF_BASE64)

    def test_embedded_resource_image_url_conversion(self):
        """Test conversion of image URL in EmbeddedResource to Anthropic image block."""
        # Create an image resource with URL
        image_resource = BlobResourceContents(
            uri="https://example.com/image.jpg",
            mimeType="image/jpeg",
            blob=self.sample_image_base64,  # This should be ignored for URL
        )
        embedded_resource = EmbeddedResource(type="resource", resource=image_resource)
        multipart = PromptMessageMultipart(role="user", content=[embedded_resource])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - using dictionary access
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "image")
        self.assertEqual(anthropic_msg["content"][0]["source"]["type"], "url")
        self.assertEqual(
            anthropic_msg["content"][0]["source"]["url"],
            "https://example.com/image.jpg",
        )

    def test_assistant_role_restrictions(self):
        """Test that assistant messages can only contain text blocks."""
        # Create mixed content for assistant
        text_content = TextContent(type="text", text=self.sample_text)
        image_content = ImageContent(
            type="image", data=self.sample_image_base64, mimeType="image/jpeg"
        )
        multipart = PromptMessageMultipart(role="assistant", content=[text_content, image_content])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - only text should remain
        self.assertEqual(anthropic_msg["role"], "assistant")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], self.sample_text)

    def test_multiple_content_blocks(self):
        """Test conversion of messages with multiple content blocks."""
        # Create multiple content blocks
        text_content1 = TextContent(type="text", text="First text")
        image_content = ImageContent(
            type="image", data=self.sample_image_base64, mimeType="image/jpeg"
        )
        text_content2 = TextContent(type="text", text="Second text")

        multipart = PromptMessageMultipart(
            role="user", content=[text_content1, image_content, text_content2]
        )

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - using dictionary access
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 3)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], "First text")
        self.assertEqual(anthropic_msg["content"][1]["type"], "image")
        self.assertEqual(anthropic_msg["content"][2]["type"], "text")
        self.assertEqual(anthropic_msg["content"][2]["text"], "Second text")

    def test_unsupported_mime_type_handling(self):
        """Test handling of unsupported MIME types."""
        # Create an image with unsupported mime type
        image_content = ImageContent(
            type="image",
            data=self.sample_image_base64,
            mimeType="image/bmp",  # Unsupported in Anthropic API
        )
        text_content = TextContent(type="text", text="This is some text")
        multipart = PromptMessageMultipart(role="user", content=[text_content, image_content])

        # Convert to Anthropic format - should convert unsupported image to text fallback
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Should have kept the text content and added a fallback text for the image
        self.assertEqual(len(anthropic_msg["content"]), 2)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], "This is some text")
        self.assertEqual(anthropic_msg["content"][1]["type"], "text")
        self.assertIn(
            "Image with unsupported format 'image/bmp'",
            anthropic_msg["content"][1]["text"],
        )

    def test_svg_resource_conversion(self):
        """Test handling of SVG resources - should convert to code block."""
        # Create an embedded SVG resource
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>'
        svg_resource = TextResourceContents(
            uri="test://example.com/image.svg",
            mimeType="image/svg+xml",
            text=svg_content,
        )
        embedded_resource = EmbeddedResource(type="resource", resource=svg_resource)
        multipart = PromptMessageMultipart(role="user", content=[embedded_resource])

        # Convert to Anthropic format - should extract SVG as text
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Should be converted to a text block with the SVG code
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertIn("```xml", anthropic_msg["content"][0]["text"])
        self.assertIn(svg_content, anthropic_msg["content"][0]["text"])

    def test_empty_content_list(self):
        """Test conversion with empty content list."""
        multipart = PromptMessageMultipart(role="user", content=[])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Should have empty content list
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 0)

    def test_embedded_resource_pdf_url_conversion(self):
        """Test conversion of PDF URL in EmbeddedResource to Anthropic document block."""
        # Create a PDF resource with URL
        pdf_resource = BlobResourceContents(
            uri="https://example.com/document.pdf",
            mimeType="application/pdf",
            blob=base64.b64encode(b"fake_pdf_data").decode("utf-8"),
        )
        embedded_resource = EmbeddedResource(type="resource", resource=pdf_resource)
        multipart = PromptMessageMultipart(role="user", content=[embedded_resource])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions - using dictionary access
        self.assertEqual(anthropic_msg["content"][0]["type"], "document")
        self.assertEqual(anthropic_msg["content"][0]["source"]["type"], "url")
        self.assertEqual(
            anthropic_msg["content"][0]["source"]["url"],
            "https://example.com/document.pdf",
        )

    def test_mixed_content_with_unsupported_formats(self):
        """Test conversion of mixed content where some items are unsupported."""
        # Create mixed content with supported and unsupported items
        text_content = TextContent(type="text", text=self.sample_text)
        unsupported_image = ImageContent(
            type="image",
            data=self.sample_image_base64,
            mimeType="image/bmp",  # Unsupported
        )
        supported_image = ImageContent(
            type="image",
            data=self.sample_image_base64,
            mimeType="image/jpeg",  # Supported
        )

        multipart = PromptMessageMultipart(
            role="user", content=[text_content, unsupported_image, supported_image]
        )

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Should have kept the text, created fallback for unsupported, and kept supported image
        self.assertEqual(len(anthropic_msg["content"]), 3)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], self.sample_text)
        self.assertEqual(
            anthropic_msg["content"][1]["type"], "text"
        )  # Fallback text for unsupported
        self.assertEqual(anthropic_msg["content"][2]["type"], "image")  # Supported image kept
        self.assertEqual(anthropic_msg["content"][2]["source"]["media_type"], "image/jpeg")

    def test_code_file_as_text_document_with_filename(self):
        """Test handling of code files using a simple filename."""
        code_text = "def hello_world():\n    print('Hello, world!')"

        # Use the helper function with simple filename
        code_resource = create_text_resource(
            text=code_text, filename_or_uri="example.py", mime_type="text/x-python"
        )

        embedded_resource = EmbeddedResource(type="resource", resource=code_resource)

        multipart = PromptMessageMultipart(role="user", content=[embedded_resource])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Check that title is set correctly
        self.assertEqual(anthropic_msg["content"][0]["title"], "example.py")
        self.assertEqual(anthropic_msg["content"][0]["source"]["data"], code_text)
        self.assertEqual(anthropic_msg["content"][0]["source"]["media_type"], "text/plain")

    def test_code_file_as_text_document_with_uri(self):
        """Test handling of code files using a proper URI."""
        code_text = "def hello_world():\n    print('Hello, world!')"

        # Use the helper function with full URI
        code_resource = create_text_resource(
            text=code_text,
            filename_or_uri="file:///projects/example.py",
            mime_type="text/x-python",
        )

        embedded_resource = EmbeddedResource(type="resource", resource=code_resource)

        multipart = PromptMessageMultipart(role="user", content=[embedded_resource])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Should extract just the filename from the path
        self.assertEqual(anthropic_msg["content"][0]["title"], "example.py")
        self.assertEqual(anthropic_msg["content"][0]["source"]["data"], code_text)

    def test_unsupported_binary_resource_conversion(self):
        """Test handling of unsupported binary resource types."""
        # Create an embedded resource with binary data
        binary_data = base64.b64encode(b"This is binary data").decode("utf-8")  # 20 bytes of data
        binary_resource = BlobResourceContents(
            uri="test://example.com/data.bin",
            mimeType="application/octet-stream",
            blob=binary_data,
        )
        embedded_resource = EmbeddedResource(type="resource", resource=binary_resource)
        multipart = PromptMessageMultipart(role="user", content=[embedded_resource])

        # Convert to Anthropic format - should create text fallback
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Should have a fallback text block
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")

        # Check that the content describes it as unsupported format
        fallback_text = anthropic_msg["content"][0]["text"]
        self.assertIn(
            "Embedded Resource test://example.com/data.bin with unsupported format application/octet-stream (28 characters)",
            fallback_text,
        )


class TestAnthropicToolConverter(unittest.TestCase):
    """Test cases for conversion of tool results to Anthropic API format."""

    def setUp(self):
        """Set up test data."""
        self.sample_text = "This is a tool result"
        self.sample_image_base64 = base64.b64encode(b"fake_image_data").decode("utf-8")
        self.tool_use_id = "toolu_01D7FLrfh4GYq7yT1ULFeyMV"

    def test_text_tool_result_conversion(self):
        """Test conversion of text tool result to Anthropic format."""
        # Create a tool result with text content
        text_content = TextContent(type="text", text=self.sample_text)
        tool_result = CallToolResult(content=[text_content], isError=False)

        # Convert to Anthropic format
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            tool_result, self.tool_use_id
        )

        # Assertions
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(anthropic_block["tool_use_id"], self.tool_use_id)
        self.assertEqual(anthropic_block["is_error"], False)
        self.assertEqual(len(anthropic_block["content"]), 1)
        self.assertEqual(anthropic_block["content"][0]["type"], "text")
        self.assertEqual(anthropic_block["content"][0]["text"], self.sample_text)

    def test_image_tool_result_conversion(self):
        """Test conversion of image tool result to Anthropic format."""
        # Create a tool result with image content
        image_content = ImageContent(
            type="image", data=self.sample_image_base64, mimeType="image/jpeg"
        )
        tool_result = CallToolResult(content=[image_content], isError=False)

        # Convert to Anthropic format
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            tool_result, self.tool_use_id
        )

        # Assertions
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(anthropic_block["tool_use_id"], self.tool_use_id)
        self.assertEqual(anthropic_block["is_error"], False)
        self.assertEqual(len(anthropic_block["content"]), 1)
        self.assertEqual(anthropic_block["content"][0]["type"], "image")
        self.assertEqual(anthropic_block["content"][0]["source"]["type"], "base64")
        self.assertEqual(anthropic_block["content"][0]["source"]["media_type"], "image/jpeg")
        self.assertEqual(anthropic_block["content"][0]["source"]["data"], self.sample_image_base64)

    def test_mixed_tool_result_conversion(self):
        """Test conversion of mixed content tool result to Anthropic format."""
        # Create a tool result with text and image content
        text_content = TextContent(type="text", text=self.sample_text)
        image_content = ImageContent(
            type="image", data=self.sample_image_base64, mimeType="image/jpeg"
        )
        tool_result = CallToolResult(content=[text_content, image_content], isError=False)

        # Convert to Anthropic format
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            tool_result, self.tool_use_id
        )

        # Assertions
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(anthropic_block["tool_use_id"], self.tool_use_id)
        self.assertEqual(len(anthropic_block["content"]), 2)
        self.assertEqual(anthropic_block["content"][0]["type"], "text")
        self.assertEqual(anthropic_block["content"][0]["text"], self.sample_text)
        self.assertEqual(anthropic_block["content"][1]["type"], "image")

    def test_pdf_result_conversion(self):
        """Test conversion of mixed content tool result to Anthropic format."""
        # Create a tool result with text and PDF content
        text_content = TextContent(type="text", text=self.sample_text)
        pdf_content = create_pdf_resource(PDF_BASE64)
        tool_result = CallToolResult(content=[text_content, pdf_content], isError=False)

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.create_tool_results_message(
            [(self.tool_use_id, tool_result)]
        )

        # Assertions
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 2)

        # First block should be a tool result with just the text content
        self.assertEqual(anthropic_msg["content"][0]["type"], "tool_result")
        self.assertEqual(anthropic_msg["content"][0]["tool_use_id"], self.tool_use_id)
        self.assertEqual(len(anthropic_msg["content"][0]["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["content"][0]["text"], self.sample_text)

        # Second block should be the document block with the PDF
        self.assertEqual(anthropic_msg["content"][1]["type"], "document")
        self.assertEqual(anthropic_msg["content"][1]["source"]["type"], "base64")
        self.assertEqual(anthropic_msg["content"][1]["source"]["media_type"], "application/pdf")
        self.assertEqual(anthropic_msg["content"][1]["source"]["data"], PDF_BASE64)

    def test_mixed_tool_markdown_result_conversion(self):
        """Test conversion a text resource (tool) Anthropic format."""
        markdown_content = EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                uri=AnyUrl("resource://test/content"),
                mimeType="text/markdown",
                text="markdown text",
            ),
        )

        # Convert to Anthropic format
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            CallToolResult(content=[markdown_content]), self.tool_use_id
        )

        # Assertions
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(anthropic_block["tool_use_id"], self.tool_use_id)
        self.assertEqual(len(anthropic_block["content"]), 1)
        self.assertEqual(anthropic_block["content"][0]["type"], "text")
        self.assertEqual(anthropic_block["content"][0]["text"], "markdown text")

    def test_binary_only_tool_result_conversion(self):
        """Test that a tool result with only binary content still returns a tool result block."""
        # Create a PDF embedded resource with no text content
        pdf_content = create_pdf_resource(PDF_BASE64)
        tool_result = CallToolResult(content=[pdf_content], isError=False)

        # First test the individual tool result conversion
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            tool_result, self.tool_use_id
        )

        # It should still have a tool_result type even if content might be empty
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(anthropic_block["tool_use_id"], self.tool_use_id)

        # Now test the message creation with this result
        anthropic_msg = AnthropicConverter.create_tool_results_message(
            [(self.tool_use_id, tool_result)]
        )

        # Should have two blocks: one tool result (even if empty) and one document
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 2)

        # First block should be the tool result
        self.assertEqual(anthropic_msg["content"][0]["type"], "tool_result")

        # Second block should be the document
        self.assertEqual(anthropic_msg["content"][1]["type"], "document")

    def test_error_tool_result_conversion(self):
        """Test conversion of error tool result to Anthropic format."""
        # Create a tool result with error flag set
        text_content = TextContent(type="text", text="Error: Something went wrong")
        tool_result = CallToolResult(content=[text_content], isError=True)

        # Convert to Anthropic format
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            tool_result, self.tool_use_id
        )

        # Assertions
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(anthropic_block["tool_use_id"], self.tool_use_id)
        self.assertEqual(anthropic_block["is_error"], True)
        self.assertEqual(len(anthropic_block["content"]), 1)
        self.assertEqual(anthropic_block["content"][0]["type"], "text")
        self.assertEqual(anthropic_block["content"][0]["text"], "Error: Something went wrong")

    def test_unsupported_image_format_in_tool_result(self):
        """Test handling of unsupported image format in tool result."""
        # Create a tool result with unsupported image format
        image_content = ImageContent(
            type="image",
            data=self.sample_image_base64,
            mimeType="image/bmp",  # Unsupported
        )
        tool_result = CallToolResult(content=[image_content], isError=False)

        # Convert to Anthropic format
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            tool_result, self.tool_use_id
        )

        # Unsupported image should be converted to text
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(len(anthropic_block["content"]), 1)
        self.assertEqual(anthropic_block["content"][0]["type"], "text")
        self.assertIn(
            "Image with unsupported format 'image/bmp'",
            anthropic_block["content"][0]["text"],
        )

    def test_empty_tool_result_conversion(self):
        """Test conversion of empty tool result to Anthropic format."""
        # Create a tool result with no content
        tool_result = CallToolResult(content=[], isError=False)

        # Convert to Anthropic format
        anthropic_block = AnthropicConverter.convert_tool_result_to_anthropic(
            tool_result, self.tool_use_id
        )

        # Should have a placeholder text block
        self.assertEqual(anthropic_block["type"], "tool_result")
        self.assertEqual(len(anthropic_block["content"]), 1)
        self.assertEqual(anthropic_block["content"][0]["type"], "text")
        self.assertEqual(anthropic_block["content"][0]["text"], "[No content in tool result]")

    def test_create_tool_results_message(self):
        """Test creation of user message with multiple tool results."""
        # Create two tool results
        text_content = TextContent(type="text", text=self.sample_text)
        image_content = ImageContent(
            type="image", data=self.sample_image_base64, mimeType="image/jpeg"
        )

        tool_result1 = CallToolResult(content=[text_content], isError=False)

        tool_result2 = CallToolResult(content=[image_content], isError=False)

        tool_use_id1 = "tool_id_1"
        tool_use_id2 = "tool_id_2"

        # Create tool results list
        tool_results = [(tool_use_id1, tool_result1), (tool_use_id2, tool_result2)]

        # Convert to Anthropic message
        anthropic_msg = AnthropicConverter.create_tool_results_message(tool_results)

        # Assertions
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 2)

        # Check first tool result
        self.assertEqual(anthropic_msg["content"][0]["type"], "tool_result")
        self.assertEqual(anthropic_msg["content"][0]["tool_use_id"], tool_use_id1)
        self.assertEqual(anthropic_msg["content"][0]["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["content"][0]["text"], self.sample_text)

        # Check second tool result
        self.assertEqual(anthropic_msg["content"][1]["type"], "tool_result")
        self.assertEqual(anthropic_msg["content"][1]["tool_use_id"], tool_use_id2)
        self.assertEqual(anthropic_msg["content"][1]["content"][0]["type"], "image")


def create_text_resource(
    text: str, filename_or_uri: str, mime_type: str = None
) -> TextResourceContents:
    """
    Helper function to create a TextResourceContents with proper URI handling.

    Args:
        text: The text content
        filename_or_uri: A filename or URI
        mime_type: Optional MIME type

    Returns:
        A properly configured TextResourceContents
    """
    # Normalize the URI
    uri = normalize_uri(filename_or_uri)

    return TextResourceContents(uri=uri, mimeType=mime_type, text=text)


class TestAnthropicAssistantConverter(unittest.TestCase):
    """Test cases for conversion from assistant role MCP message types to Anthropic API."""

    def setUp(self):
        """Set up test data."""
        self.sample_text = "This is a response from the assistant"

    def test_assistant_text_content_conversion(self):
        """Test conversion of assistant TextContent to Anthropic text block."""
        # Create a text content message from assistant
        text_content = TextContent(type="text", text=self.sample_text)
        multipart = PromptMessageMultipart(role="assistant", content=[text_content])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions
        self.assertEqual(anthropic_msg["role"], "assistant")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], self.sample_text)

    def test_convert_prompt_message_to_anthropic(self):
        """Test conversion of a standard PromptMessage to Anthropic format."""
        # Create a PromptMessage with TextContent
        text_content = TextContent(type="text", text=self.sample_text)
        prompt_message = PromptMessage(role="assistant", content=text_content)

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_prompt_message_to_anthropic(prompt_message)

        # Assertions
        self.assertEqual(anthropic_msg["role"], "assistant")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], self.sample_text)

    def test_convert_prompt_message_image_to_anthropic(self):
        """Test conversion of a PromptMessage with image content to Anthropic format."""
        # Create a PromptMessage with ImageContent
        image_base64 = base64.b64encode(b"fake_image_data").decode("utf-8")
        image_content = ImageContent(type="image", data=image_base64, mimeType="image/jpeg")
        prompt_message = PromptMessage(role="user", content=image_content)

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_prompt_message_to_anthropic(prompt_message)

        # Assertions
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "image")
        self.assertEqual(anthropic_msg["content"][0]["source"]["type"], "base64")
        self.assertEqual(anthropic_msg["content"][0]["source"]["media_type"], "image/jpeg")
        self.assertEqual(anthropic_msg["content"][0]["source"]["data"], image_base64)

    def test_convert_prompt_message_embedded_resource_to_anthropic(self):
        """Test conversion of a PromptMessage with embedded resource to Anthropic format."""
        # Create a PromptMessage with embedded text resource
        text_resource = TextResourceContents(
            uri="test://example.com/document.txt",
            mimeType="text/plain",
            text="This is a text resource",
        )
        embedded_resource = EmbeddedResource(type="resource", resource=text_resource)
        prompt_message = PromptMessage(role="user", content=embedded_resource)

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_prompt_message_to_anthropic(prompt_message)

        # Assertions
        self.assertEqual(anthropic_msg["role"], "user")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "document")
        self.assertEqual(anthropic_msg["content"][0]["source"]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["title"], "document.txt")
        self.assertEqual(anthropic_msg["content"][0]["source"]["data"], "This is a text resource")

    def test_assistant_multiple_text_blocks(self):
        """Test conversion of assistant messages with multiple text blocks."""
        # Create multiple text content blocks
        text_content1 = TextContent(type="text", text="First part of response")
        text_content2 = TextContent(type="text", text="Second part of response")

        multipart = PromptMessageMultipart(role="assistant", content=[text_content1, text_content2])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Assertions
        self.assertEqual(anthropic_msg["role"], "assistant")
        self.assertEqual(len(anthropic_msg["content"]), 2)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], "First part of response")
        self.assertEqual(anthropic_msg["content"][1]["type"], "text")
        self.assertEqual(anthropic_msg["content"][1]["text"], "Second part of response")

    def test_assistant_non_text_content_stripped(self):
        """Test that non-text content is stripped from assistant messages."""
        # Create a mixed content message with text and image
        text_content = TextContent(type="text", text=self.sample_text)
        image_content = ImageContent(
            type="image",
            data=base64.b64encode(b"fake_image_data").decode("utf-8"),
            mimeType="image/jpeg",
        )

        multipart = PromptMessageMultipart(role="assistant", content=[text_content, image_content])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Only text should remain, image should be filtered out
        self.assertEqual(anthropic_msg["role"], "assistant")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], self.sample_text)

    def test_assistant_embedded_resource_stripped(self):
        """Test that embedded resources are stripped from assistant messages."""
        # Create a message with text and embedded resource
        text_content = TextContent(type="text", text=self.sample_text)

        resource_content = TextResourceContents(
            uri="test://example.com/document.txt",
            mimeType="text/plain",
            text="Some document content",
        )
        embedded_resource = EmbeddedResource(type="resource", resource=resource_content)

        multipart = PromptMessageMultipart(
            role="assistant", content=[text_content, embedded_resource]
        )

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Only text should remain, resource should be filtered out
        self.assertEqual(anthropic_msg["role"], "assistant")
        self.assertEqual(len(anthropic_msg["content"]), 1)
        self.assertEqual(anthropic_msg["content"][0]["type"], "text")
        self.assertEqual(anthropic_msg["content"][0]["text"], self.sample_text)

    def test_assistant_empty_content(self):
        """Test conversion with empty content from assistant."""
        multipart = PromptMessageMultipart(role="assistant", content=[])

        # Convert to Anthropic format
        anthropic_msg = AnthropicConverter.convert_to_anthropic(multipart)

        # Should have empty content list
        self.assertEqual(anthropic_msg["role"], "assistant")
        self.assertEqual(len(anthropic_msg["content"]), 0)
