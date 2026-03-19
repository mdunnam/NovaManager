"""
OpenCV-based image retouching for automated blemish removal.
"""
import cv2
import numpy as np
from pathlib import Path


class ImageRetoucher:
    """Handles automated retouching using OpenCV inpainting algorithms."""
    
    def __init__(self):
        pass
    
    def apply_blemish_removal(
        self,
        image_path,
        annotations,
        output_path=None,
        algorithm='telea',
        inpaint_radius=3,
        mask_padding=2,
    ):
        """
        Apply inpainting to remove blemishes marked by circle annotations.
        
        Args:
            image_path: Path to the source image
            annotations: List of annotation dicts (from vector_annotations.json)
            output_path: Where to save the retouched image (optional)
            algorithm: 'telea' (fast, good for small areas) or 'ns' (Navier-Stokes, better for larger areas)
            inpaint_radius: Radius used by cv2.inpaint
            mask_padding: Extra pixels to pad each blemish mask region
        
        Returns:
            Tuple of (success: bool, output_path: str or None, message: str)
        """
        try:
            # Load image
            img = cv2.imread(str(image_path))
            if img is None:
                return False, None, "Could not load image"
            
            # Create mask for all blemish annotations
            mask = np.zeros(img.shape[:2], dtype=np.uint8)
            blemish_count = 0
            
            for ann in annotations:
                if ann.get("type") != "circle":
                    continue
                if ann.get("layer") != "blemish":
                    continue
                
                x1, y1 = int(ann.get("x1", 0)), int(ann.get("y1", 0))
                x2, y2 = int(ann.get("x2", 0)), int(ann.get("y2", 0))
                
                # Draw filled ellipse on mask
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                radius_x = abs(x2 - x1) // 2
                radius_y = abs(y2 - y1) // 2
                
                # Add small padding to ensure good coverage
                radius_x = max(3, radius_x + int(mask_padding))
                radius_y = max(3, radius_y + int(mask_padding))
                
                cv2.ellipse(mask, (center_x, center_y), (radius_x, radius_y), 0, 0, 360, 255, -1)
                blemish_count += 1
            
            if blemish_count == 0:
                return False, None, "No blemish annotations found to process"
            
            # Apply inpainting
            if algorithm.lower() == 'ns':
                result = cv2.inpaint(img, mask, inpaintRadius=float(inpaint_radius), flags=cv2.INPAINT_NS)
            else:  # telea (default)
                result = cv2.inpaint(img, mask, inpaintRadius=float(inpaint_radius), flags=cv2.INPAINT_TELEA)
            
            # Determine output path
            if output_path is None:
                base = Path(image_path)
                output_path = base.parent / f"{base.stem}_retouched{base.suffix}"
            
            # Save result
            output_path = Path(output_path)
            cv2.imwrite(str(output_path), result)
            
            return True, str(output_path), f"Retouched {blemish_count} blemish(es)"
            
        except Exception as e:
            return False, None, f"Retouch error: {str(e)}"
    
    def preview_mask(self, image_path, annotations):
        """
        Generate a preview of what will be inpainted (for debugging).
        
        Returns:
            numpy array of the mask, or None on error
        """
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return None
            
            mask = np.zeros(img.shape[:2], dtype=np.uint8)
            
            for ann in annotations:
                if ann.get("type") != "circle":
                    continue
                if ann.get("layer") != "blemish":
                    continue
                
                x1, y1 = int(ann.get("x1", 0)), int(ann.get("y1", 0))
                x2, y2 = int(ann.get("x2", 0)), int(ann.get("y2", 0))
                
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                radius_x = abs(x2 - x1) // 2 + 2
                radius_y = abs(y2 - y1) // 2 + 2
                
                cv2.ellipse(mask, (center_x, center_y), (radius_x, radius_y), 0, 0, 360, 255, -1)
            
            return mask
            
        except Exception:
            return None
