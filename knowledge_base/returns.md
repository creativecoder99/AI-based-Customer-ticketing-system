# Returns Policy

## Overview
This policy details customer rights and guidelines for standard product returns.

## Return Window
- Standard items can be returned within **30 calendar days** from the delivery date for a full product refund or exchange (`APPROVE_RETURN`).
- Return requests initiated beyond the 30-day window cannot be accepted under standard policy and must be rejected (`REJECT_REQUEST`).

## Condition Requirements
- Items must be brand new, unworn, unwashed, with all original tags attached, and packed in their original retail packaging.
- Items showing signs of wear, damage from misuse, or altered tags will be returned to the sender without refund.

## Excluded & Non-Returnable Products
- Items explicitly marked as "Final Sale", "Clearance", or sold during seasonal closeouts are non-returnable (`REJECT_REQUEST`).
- Customized, monogrammed, or personalized merchandise cannot be returned.
- Intimate apparel, hygiene-sealed products, and perishable goods are exempt from returns.

## Return Shipping & Fees
- Standard returns require the customer to print a return authorization slip and drop off the package at an authorized courier hub.
- Return shipping fees are waived for defective or incorrect items dispatched by the warehouse.

## Incorrect or Mismatched Item Delivered
- If a customer receives an incorrect, wrong, or mismatched item (e.g. ordered a phone or electronics, but received shoes, apparel, or a different item):
  - Customers must provide clear photographs of the incorrect item received and the courier shipping label (`REQUEST_PHOTOS`).
  - Once photographic evidence is submitted and verified, customer support will immediately approve a free return and refund (`APPROVE_REFUND`) or dispatch a priority replacement.

## Unidentified or Incomplete Requests
- If the return request does not specify the delivery date, item condition, or reasons for return, the team must ask for further details (`NEEDS_MORE_INFORMATION`).
