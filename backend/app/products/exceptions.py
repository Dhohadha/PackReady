class ProductNotFoundError(Exception):
    """
    Raised when a product is not found.
    """
    pass


class CategoryNotFoundError(Exception):
    """
    Raised when a category is not found.
    """
    pass


class ImageNotFoundError(Exception):
    """
    Raised when a product image metadata is not found.
    """
    pass


class StorageFileNotFoundError(Exception):
    """
    Raised when an image file is not found in local storage.
    """
    pass
