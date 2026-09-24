import math

FEE_DEN = 1_000_000

# a pool holds reserves x and y
# x is the reserve of the token you're putting in
# y is the reserve of the token you're taking out
# dx is how much you give
def get_amount_out(x, y, dx, f):
    dx_eff = dx * (1 - f) # fee
    
    k = x * y # calculating the constant 
    
    new_x = x + dx_eff # calculating the new x reserve
    new_y = k / new_x # calculating the new y reserve
    dy = y - new_y # what you take out
    
    return dy

# i want exactly dy, how many x must i bring?
# after the trade, the pool has (y - dy) of token y
# the rule says x must then be k / (y - dy)
# the x you add are that minus x. dx_eff
# then to undo the fee dx = dx_eff / (1 - f)
def get_amount_in(x, y, dy, f):
    if dy >= y:
        raise ValueError("can't take out the whole reserve or more")
    
    k = x * y 
    
    new_x = k / (y - dy) # the x reserve 
    
    dx = (new_x - x) / (1 - f)

    return dx    

def get_amount_out_int(x, y, dx, fee_num=25, fee_den=FEE_DEN):
    dx_eff = dx * (fee_den - fee_num) // fee_den
    
    k = x * y
    
    new_x = x + dx_eff
    new_y = k // new_x
    return y * dx_eff // (x + dx_eff)
    

def get_amount_in_int(x, y, dy, fee_num=25, fee_den=FEE_DEN):
    if dy >= y:
        raise ValueError("can't take out the whole reserve or more")
    
    k = x * y 
    
    new_x = -(-k // (y - dy))
    
    dx_eff = new_x - x
    
    return -(-(dx_eff * fee_den) // (fee_den - fee_num))