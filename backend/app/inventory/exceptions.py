class InventoryNotFoundError(Exception):
    """
    Raised when an inventory record is not found.
    """
    pass


class InsufficientStockError(Exception):
    """
    Raised when stock-out quantity exceeds current inventory.
    """
    pass
