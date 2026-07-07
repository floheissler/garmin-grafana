"""MCP Server for querying Garmin health data from InfluxDB."""

import hmac
import json
import os
from typing import Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import Icon

from .db import db
from .queries import (
    AggregationType,
    build_activities_query,
    build_daily_stats_query,
    build_select_query,
    build_sleep_query,
    get_time_range,
)
from .formatters import (
    format_activities_list,
    format_activity_details,
    format_blood_pressure,
    format_body_composition,
    format_daily_summary,
    format_fitness_metrics,
    format_heart_rate_data,
    format_hrv_data,
    format_sleep_data,
    format_stress_body_battery,
    format_training_status,
)

BATSERVER_ICON = (
    "data:image/png;base64,"
    "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"
    "SQhZWlpMpxOEkJ2d7a2tTULIwUF+fX2dEJLP5y8cMoZXV5cJIY1GfWlpQdNUwzBmZ2epAHl+fi6V"
    "2qf419B1Xdd0Xc+k06lUUtfVw8NcLpfRNK1QOEql0pqmFovFTCat61qhcJROp3VdKxTyBwdZTdPy"
    "+WwqlTQMvVgsZDJpw9Dz+YODg6ymafn8QSaTNgw9l8tmMhlN0/L5g3Q6rWlaPp/P5XKqquZyuUwm"
    "bRhGoZDPZjO6rhcK+UzmwDCMfD6Xy2V0XS8U8rlcVlXVXC6bzeZ0Xc/lcrlsVtP0YrGQy+V0XT84"
    "yGezGV3XS6ViPp/TdT2fz+dyeV3Xi8ViPp/XdT2Xy+VyWV3X8/lcPp/TdS2fzx8c5DRNO8jns9ms"
    "rmuFQqFQyKuqlstls9msqqq5XDaXy2qa1r8/l9N1vVgsZLNZVVVzuWw+n9M0rVTK5/M5TdOy2Uw2"
    "m9E0/eAgm81mdF0vFPIHB1ld14vFYj6f03U9n8/ncjld17PZbD6f0zQtn88fHOQ0Tc/n87lcTtf1"
    "YrGQy+U0TTs4yGYyGV3Xi8VCLpfTdD2fz+dyOU3Tc7lcNpvRNK1YLORyOVVVc7lsNpvRNL1YLOQL"
    "eV3X8vlcPp9XVTWXO8jlspqmlUqF/EFe17VcLpvN5TRNz+dy2WxW1/VCIZfLZVVVzWaz2WxW07Ri"
    "sZDP5TVNO8jnDg6yhmHk87n8QU7TtHw+l8/ndF0vFvP5fE7T9Gw2k81mNU0vFguFQl7X9WIxXyjk"
    "dV3L5bK5XFbX9UIhn8/nNE3L57PZbFbX9Xw+n8vldF0vFguFQl7X9UIhf3CQ0zQtl8tls1lN0wuF"
    "fD6f03Utn8/l8zld14vFQqGQ1zStkM/nc3ld13K5bC6X1XW9UMjnchd4l0Ihl8/nNE3L5/PZXE7T"
    "9EKhkM/ndF3P53O5fE7X9WKxkM/ndV0vFPK5XE7X9UIhXyjkdV3L5bK5XFbT+u0fHOQ0TcvlsrlC"
    "XtO0YjGfz+U0TcvlctlsVtf1YrGQz+c1TS8UCvl8Tte1fD6fy+U0TcvlstlsRte1YrFQKOR1Xc/l"
    "ctlsVte1YrFYKOR1XS8U8oVCXte1XC6by+V0XS8W84VCXtf1QiFfKOR1XSsU8oVCTtf1fD6fy+d0"
    "XS8W84VCXtO0fD6fy+V0Xc/n8/l8Tte1fD6Xy+V0Xc/ns7lcTtf1YrGQz+c1TcsX8vl8Ttf1QiFf"
    "KOR1XS8U8vl8Xtf1QuGgUMjrupbPZ3O5nK5rhUI+n8/pul4s5guFvKZpuVw2m83qul4sFgqFvK7r"
    "xWIhn89rmpbP57PZLF1i+Xw+l8vpul4sFgr5vKbp+Xw+l8vpul4sFouFvK7rxWKhUMjrul4sFgqF"
    "vK7rxWKhUMjrulYo5AuFvK7rhUIhX8jrulYo5AsFGlzl84V8Ia/req6Qy+dzuq4Xi4VCIa9perGY"
    "LxTyuq7n87l8Pqfrer6Qz+dzuq4XCoVCoaDrer6Qz+fzmqbn87lcLqfrWqGQLxTyuq4Xi/lCIa/r"
    "er5QyBfyuq4XCoVCoaDreqFQKBTymqYXi8ViMa/req7f/oGu68VioVDIa5qez+dzuZyu64VCoVDI"
    "67qez+fz+byu68VivlDI67peKOQLhbyu64VCoVDI67qeL+QLhbyu68VioVDI67peKBQKhYKu68Vi"
    "oVjM67qez+dzuZyuG8ViIV/I67qWz+dyuZymGf3+5PN5XdfzhXyxmNd1PZfL5XJ5TdPz+Xw+n9d1"
    "PZ/P5/N5TdNzuWwul9U0vVjMFwp5XdcLhXyhkNd1vVAoFAoFXdfz+Vwul9N1vVgsFAp5XdeLxXyx"
    "mNc0LZ/PZ7NZTdOLxUKhkNd1vVAo5At5XdeLxUKxWNB1vVjMFwp5TdPz+Xw2m9M0PZ/PZ7NZTdOL"
    "xUIhn9d1PZ/P5XI5XdeLxUKhkNc0PZ/PZbNZTdOLxUIhn9c0PZ/P53I5XdeLxUKhkNc0PZ/PZ7MZ"
    "TdNLpWKhkNd1vVgs5At5TdPz+Xwul9N1LZ/P5fN5TdPz+Xw+n9N1PZ/P5/M5TdPz+Xw+n9c0LZ/P"
    "5fN5TdPy+Vw+n9d1PZ/P5fI5TdOLxUKhkNc0LZ/P53I5TdNLpWKxmNc0PZ/P53I5TdNKpVKxmNd1"
    "vVgs5At5TdPz+Xwul9M0rVQqFot5TdPy+Xwul9M0vVQqFot5TdNKpVKxmNd1vVQqFYt5XddLpWKx"
    "mNd1LZ/P5fN5XddLpVKxWNB1rVDIFwp5XddLpVKxWNB1rVDI5ws5XddLpWKxWNB1rVDI5ws5Xdfy"
    "+Vw+n9d1PZ/P5fN5TdNKpVKxWNB1vVQqFYt5XddLpWKxWNB1rVQqFYt5TdOLxUKhkNd1vVQqFor5"
    "/u+bVCqVikW9//tmJaNpWqlUKhbzuq4Xi4VCIa/reqlUKhaLuq6XSqVSqaDreqlUKhb1/v2lUrFU"
    "LOi6ls/ncvmcpmn5fC6fz+u6XigUCoW8pumlUqlULOi6XiqVSqWiruulUrlcKui6Xi6Xy+WCruuV"
    "SrlcLuq6Xi6Xy+WCruuVSqVcLui6XqlUyuWCrmvlcrlcLui6XiqVSqWiruulUrlcLuq6Xi6Xy+WC"
    "ruuVSqVcLui6Xi6XyuWCruuVSqVcLum6Xi6Xy+WSruvlcrlcLuu6Xi6XSqWSruulUrlUKuq6Xi6X"
    "yuWSruuVSqVSKem6XiqVSqWiruuVSqVSKem63v+8VNJ1vVKpVColXddLpVKpVNR1vVwul8tFXdcr"
    "lUq5XNJ1vVIpl8slXdcrlUqlUtJ1vVKpVColXdcrlUqlUtJ1vVKpVEolXdfL5XK5XNR1vVKpVCol"
    "XdfL5UqlUtJ1vVqtVCpFXdcrlXKlUtJ1vVqtVColXder1UqlUtR1vVqtVipFXder1WqlUqT3VyqV"
    "SqWo63qlUqlUirquVyqVSqWo63qlUqlUirqul8vlcrmk63q5XC6Xi7qul8vlcrmk63q5XC6XS7qu"
    "l0qlUqmo63q5XCqVSrqul0qlUqmk63q5XCqVSrqul0qlcrmk63q5XC6Xi7quVyqVSqWk63q5XC6X"
    "i7qul8vlcrmk63q5XC6XS7qul8vlcrmk63q5XK6Ui7qul8vlcrmo63qlUqlUSrqul8vlcqWk63q5"
    "XC6XS7qul8vlcrms63q5XK5USrqul8uVSqWs63q1WqmUy7quV6vVarmk63qlUqmUS7quV6vVarWk"
    "63q1Wq2US7quV6uVapmOP1+pVCslXder1Wq1UtZ1vVqtVisVXder1Wq1UtF1vVqtVitlXder1Uq1"
    "UtZ1vVarVatlXder1Wq1UtZ1vVarVqtlXder1UqlXNZ1vVqtVisVXdfL5UqlUtJ1vVwuV8olXddL"
    "pXK5pOt6pVKpVEq6rpdKpXJJ1/VKpVIp6bpeqVTKZV3XK5VKpazrerlcrpR1Xa9WK5Wyruv9z0sl"
    "Xdcr5XKlXNJ1vVKpVMplXdfL5XKlXNZ1vVqtVstlXder1Wq1UtZ1vVarVislXder1Wq1XNZ1vVar"
    "1WpZ1/VarVarlXVdr1ar1WpZ1/VarVatVnRdr9Wq1WpF1/V6vVarlXVdr9eq1WpV1/VarVqrVnRd"
    "r9Vq1Wpl+1//+t/gec97LgBgf39/e3ubEJJKJZeXlwkhrVZrdnbWMAzD0OfmZpvNBiFkeXk5nUkR"
    "Qra3t3Z2tgkh2Wx2bW2VEFKL/xdccMkl97/yiiu+9KUvLS4uAEJIq9VaXV02DMPQ9YXF+Wq1Qghd"
    "XFQfvbOzRfXcmUxqcXGeENJoNJaXl0zTsCxrfn6u0agTQlZXV/L5A0LI/t4u1U9nMpnFxQWYzWY5"
    "jud4Xu0pBBC/f9B1bMdxZVmybUvTNL/fDwDodDqyLHIc31M6LMuIomQYOoJIkj22bVuWKcuyizHd"
    "hQRBtCwLY1eWPa7rGoYuSRIApNfrybJHlmVFUURBIgC7LhYFAUGEOp2O49hDQ0O6rmuaGgqFXRe3"
    "2+1gKMTzfKNR93q9sixXKhWO48LhcLvdxhiHQqGe0jMtKxwKuS5utVrBYIhhmFq95vHIHo+nVqsJ"
    "guDz+9vtNsuyQ0OBVqvlOG4oFNJ0Tdd0v38AQtTpdCVJFASx1+uxLOMfGGi329jFIyMj3W6n2+0G"
    "g0HXdRuNht8/IIpitVrleT4cHm42m67rhkIhRVF7PS0UCtmO0263gkNBhJhqteb1yr6Bfn9EURRF"
    "aWgoaJpWs9UKBoOCINTrdb/f7/f7q9UqL/ChcKjVarmuGw6Fe4qi9JRgcMi27VarFQqFWJatVCpe"
    "r+zxeGq1miAIoVC43W67jjscHjYMo9lsBINBjuPq9brPJ/t8vnq9IQhCOBxutzuYuMHgkKIoqqoF"
    "g0HbdlqtVjAYYhim/z7zeby+Wq3Gc3w4PNxsNjHGoVBI0zRd10OhsGEYzWZzKBjkeaFer/v9/oEB"
    "f61eZxg2FAo1Gg3XdUOhkKIoPUUJhUKO47Ra7VAoxPN8vV4fGPAPDAzUajWO40KhUKPRwBiHQiFV"
    "VTVdD4XChqE3Go1wOCQIYr1e93q9sizXanVBEEKhcKvVchwnFArpum4Y+p133HF4mB0dHYlGI/t7"
    "+6IoRKMj6XSGng6XTKV0Q5ucjJfL5UqlMjU1bZp2Pp+fmpqSZSmR2A+Hh6OR6P7enixLk5OxbDan"
    "G3osHq9UKqVyKRaL6bqRyaTj8SlB4JP7ici/3uIAACAASURBVJGRSGQ0kkwmZUmKxeL0fLhYPF6r"
    "Vmv1WjwW03Ujk8lNTk5yHJdK7Y+MRCKRSCqVkkRhcnIyk80ahr+/HvIHsdhUuVypVirxeJye75lM"
    "pSYm4oLAJ5P7kUgkOhJNJpOiKExOxjKZjGnZsVisWq2WS+V4fMow9HQ6MzU1JUlSMpmKjkTCwzDz"
    "R0Y5r9crS5LqOOxrXvOaVrulaqqqqqqqVqtVVVVzudz29jZxXXB4eFAqlVRNzWazW1vblmVxHPep"
    "T37qBz/8YSCAY5+FLjA2FdQyDPO2t72VZdmt7c1cLlcqFU+fPkUxtSSIoiShRqPpOm4gEDAMvdvt"
    "ejwey7IcxwoEAhi73a5C8+NKr8cwjCjJlmU6tuvz+R3H0XUtOBR0HEfX9OHhYYEXDg4LXo/s8/l0"
    "XeN5IRgc0jStXC5/5rOf+ea3vvnLX/yCYBdjfO211/z63t/c+tVbr3/ndaurawCAy5/57G63m8vl"
    "yuVytVatVivFYqFWrZRKxWKxUCzmS6V8Pp+tVCrFUrFcLhaL+UIhX8jnCoV8sVgslfL5fL5UKhYK"
    "hVIpn8/nCoV8sVgoFgulUrlcLhYK+UIhXyzmC4VcoZArFvOlUqlYLBSLhVKpUCzmCoVcsZgvlYql"
    "UrFUKpaKhWIxXyzmS6VisVgoFgvFYqFUKpZKhWIxXywWisV8sVgolYqlUrFUKhRLhWKxUCwWSqVC"
    "sVgoFgvFYqFUKhZLxWKpUCoVS6VCqVQolYqlUrFUKpRKxVKpWCoVSqViqVQslQqlUrFUKpZKxVKp"
    "VCoVS6VSuVwqlUulUqlULpfK5VKpVC6Xy+VyqVQul0vlcqlcLpXK5VK5XCqVS+VyuVwulcrlUrlc"
    "KpfL5XKpXC6Xy6VyuVQulcrlUrlcKpVL5XK5XC6VyqVyuVQulUrlUqlcLpXK5VKpXC6XSuVyuVwu"
    "l8rlcrlcLpXK5XKpXC6XSuVyuVIulcrVcrlULpfK5VK5XCqVy+VyuVwul8vlcrlcLpfL5UqlXK6U"
    "yuVSuVwql0vlcrlcLpfL5Uq5UimXK+VyqVwulcvlUrlcKpfKpXK5XC6Xy+VKpVKpVMqVSqVSqVwq"
    "l8vlUrlcKpXL5XK5Ui6XK+VypVIqlcvlUrlcKpfL5Uq5UqmUK5VypVIql8vlUrlcKpfL5XKlUqlU"
    "ypVKpVwul0rlcqlcLpfLlUqlUqlUKpVypVIplUvlcrlSqVQq5UqlXKmUy+VSuVwuVyqVSqVSqVQq"
    "lUqlUqlUKpVKpVKpVCqVSuVSuVQqlUrlcqlcrlQq5UqlXKmUK5VSuVyuVCqVSqVSrlQq5UqlXKlU"
    "KpVKuVKpVCqVcrVSqVQqpVKpVCqVSqVSqVQqlUrlcqlULpfK5XKlUqlUKuVKpVyplCuVUqVSrlTK"
    "lUq5UilXKuVKpVypVMqVSrlSKVcq5UqlXKmUK5VypVKpVMqVSrlSKVcq5UqlXKmUK5VKpVIpVyrl"
    "SqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZTL5XKlUq5UypVKuVIpV8rlSqVcqZQrlXKlUq5UypVK"
    "uVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKl"
    "Uq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpV8rlSqVc"
    "qZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIp"
    "VyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5U"
    "ypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQr"
    "lXKlUq5UypVKuVIpV8rlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrl"
    "SqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVK"
    "uVIpVyrlSqVcqZQrlXKlUq5UypVKuVIpVyrlSqVcqZQrlXKlUq5UypVKuVKplCuVcqVSrlTKlUq5"
    "UilXKuVKpVyplCuVcqVSrlTKlXK5UilXKuVKpVyplCuVcqVSqVQqlUqlUqlUKpVKpVKpVCqVSuVS"
    "uVQqlUqlUrlcKpVKpVKpVCqVSuVSuVQqlUqlcqlcLpXK5VKpXC6Vy+VyuVIpVyrlSqVSKZVL5XKp"
    "XC6VS+VyuVIuVyqVSqVULpXL5VK5XCqXy+VypVKpVMqVSrlSKZfL5VK5XCqXS+VypVKuVMqVSrlS"
    "KZdL5XKpXC6VS+VyuVyulMuVSqVSKZVL5XK5XCqXy+VyuVwul8uVcrlSqZRKpXKpXC6XyuVyqVwu"
    "l8vlcrlcKZfLlUqpVCqVSuVyqVwqlcvlUrlcKpVL5VK5Ui6XK+VSpVIqlUrlUqlULpfK5VKpXC6V"
    "y+VyuVwpVyqVSqVcKpVK5VKpXC6Vy+VyuVyulMuVSqVSKZXK5XKpXC6Vy+VSuVwuV8qVSqVSKZVK"
    "pXK5VCqXS+VyuVwuV8rlSqVSKZVK5XK5VCqXy+VyuVwuV8qVSqVSKZVK5XK5VCqXy6VyuVQql0vl"
    "crlSqVQq5UqlXKmUS+VyuVwqlcvlUrlUKpfKpXK5Ui6XK+VypVIql0vlcrlcKpfL5XK5XC6XK+VK"
    "pVIqlUrlcqlULpfK5VKpXC6Vy+VKuVypVCqVUqlULpVK5VKpXC6VyuVyuVIuV8qVSqVSKpfKpXK5"
    "VCqXy6VyuVQul8rlcqVSqVRKpVK5VCqXS6VyuVQql8vlcrlcqZQrlUqpVCqXSuVSqVwulUulcrlU"
    "LpfK5XK5UqlUKuVKuVwqlUqlUrlUKpVK5VKpVC6Xy6VyuVSulMuVSqVcqZRK5XKpXCqVyqVyqVQu"
    "lUrlcqlcrlQqlUqlXKmUK5VSuVQul0rlcqlcLpXK5XKlUqlUypVKuVIplUrlcqlcKpXKpXK5VC6X"
    "y+VKpVKplCuVUqlcLpdLpXKpXCqVy6VyuVQul0rlcqVSqVQqlUrlUrlcKpXKpXK5VC6Xy+VyuVwu"
    "V8qVSqVcqZQrlXK5VCqVy6VyuVwql0vlcrlcrlQqlUq5UilXKuVKpVwql0vlcqlcLpXL5XK5UqlU"
    "KuVKpVwplUrlcqlULpVK5VK5XC6Xy+VypVyuVCqVSqVcKZdL5VKpXCqXyuVSuVQul8vlcqVcqVQq"
    "lVKpXC6VyqVyqVQulcrlUrlcKpfL5UqlUqlUKpVKpVKpVCqVSuVSuVQqlUqlUrlUKpVKpVKpVCqV"
    "SuVSuVQqlUqlcrlUKpVKpVKpVCqVSuVSuVQqlUqlUrlUKpVKpVKpVCqVSuVSuVQqlUqlUrlUKpVK"
    "pVKpVCqVSuVSuVQqlUqlcqlUKpVKpVKpVCqVSqVSqVQqlUqlUqlUKpVKpVKpVCqVSqVSqVQqlUrl"
    "cqlUKpVKpVKpVCqVSqVSqVQqlUqlUqlUKpVKpVKpVCqVSqVSqVQqlUrlcrlcKpVKpVKpVCqVSuVS"
    "uVQqlUqlUrlcKpVKpVKpVCqVSuVSuVQqlUqlUrlcKpVKpVKpVCqVSuVSuVQqlUqlUrlcKpVKpVKp"
    "VCqVSuVSuVQqlUrlcrlcKpVKpVKpVCqVSuVSuVQqlUrlcqlcKpVKpVKpVCqVSuVSuVQqlUrlcqlU"
    "KpVKpVKpVCqVSuVSuVQqlUrlcqlUKpVKpVKpVCqVSuVSuVQqlUrlcqlUKpVKpVKpVCqVSuVSuVQq"
    "lUrlcqlUKpVKpVKpVCqVSuVSuVQqlUrlcqlUKpVKpVKpVCqVSuVSuVQqlUrlcqlUKpVKpVKpVCqV"
    "SuVSuVQqlUrlcqlUKpVKpVKpVCqVSuVSuVQqlUrlcqlUKpVKpVKpVCqVSqVSqVQqlUqlUrlUKpVK"
    "pVKpVCqVSqVSqVQqlUqlUrlcKpVKpVKpVCqVSqVSqVQqlUqlUrlcKpVKpVKpVCqVSqVSqVQqlUrl"
    "crlUKpVKpVKpVCqVSqVSqVQqlUrlcrlUKpVKpVKpVCqVSqVSqVQqlUrlcrlcKpVKpVKpVCqVSuVS"
    "qVQqlUrlcrlUKpVKpVKpVCqVSuVSuVQqlUrlcrlUKpVKpVKpVCqVSuVSuVQqlUrlcrlcKpVKpVKp"
    "VCqVSuVSuVQqlUrlcrlcKpVKpVKpVCqVSuVSuVQqlUrlcrlcKpVKpdL/A5EbBaxNmmpi"
    "AAAAAElFTkSuQmCC"
)

# Initialize MCP server
mcp = FastMCP(
    "garmin-health",
    instructions="Query Garmin health and fitness data from InfluxDB. Use tools like get_daily_summary, get_sleep, get_heart_rate, get_activities to retrieve health metrics.",
    icons=[Icon(src=BATSERVER_ICON, mimeType="image/png", sizes=["96x96"])],
)


@mcp.tool()
def get_daily_summary(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get daily health metrics summary (steps, heart rate, stress, etc.).

    Args:
        date: Single date in YYYY-MM-DD format (e.g., "2026-01-24")
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d", "3m", "1y" (from now)

    Returns:
        Daily metrics including steps, distance, resting HR, calories, body battery, stress.
        For multi-day queries, includes statistics and trends.

    Examples:
        - get_daily_summary(date="2026-01-24") - Single day
        - get_daily_summary(duration="7d") - Last 7 days
        - get_daily_summary(start_date="2026-01-01", end_date="2026-01-31") - January 2026
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query = build_daily_stats_query(start, end)
    data = db.query(query)
    result = format_daily_summary(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_sleep(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get sleep data including score, stages, HRV, and breathing rate.

    Args:
        date: Single date in YYYY-MM-DD format for that night's sleep
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d" (from now)

    Returns:
        Sleep score, duration, stage breakdown (deep/light/REM/awake),
        HRV, stress during sleep, and breathing rate.

    Examples:
        - get_sleep(date="2026-01-24") - Last night's sleep
        - get_sleep(duration="7d") - Last week's sleep data
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query = build_sleep_query(start, end)
    data = db.query(query)
    result = format_sleep_data(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_heart_rate(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
    aggregation: AggregationType = "auto",
) -> str:
    """
    Get heart rate data with smart aggregation based on time range.

    Args:
        date: Single date in YYYY-MM-DD format
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d", "3m" (from now)
        aggregation: "auto" (default), "raw", "hourly", "daily", or "weekly"

    Returns:
        Heart rate data. Auto-aggregation:
        - 1 day: raw data (~720 points)
        - 2-7 days: hourly averages
        - 8-30 days: daily averages
        - 31+ days: weekly averages

    Examples:
        - get_heart_rate(date="2026-01-24") - Today's HR, raw
        - get_heart_rate(duration="30d") - Last month, daily averages
        - get_heart_rate(duration="7d", aggregation="raw") - Force raw data
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query, agg_info = build_select_query(
        measurement="HeartRateIntraday",
        fields=["HeartRate"],
        start=start,
        end=end,
        aggregation=aggregation,
    )
    data = db.query(query)
    result = format_heart_rate_data(data, agg_info)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_stress_body_battery(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
    aggregation: AggregationType = "auto",
) -> str:
    """
    Get stress levels and body battery data with smart aggregation.

    Args:
        date: Single date in YYYY-MM-DD format
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d" (from now)
        aggregation: "auto" (default), "raw", "hourly", "daily", or "weekly"

    Returns:
        Stress levels (0-100, -1 during activity) and body battery (0-100).
        Auto-aggregates based on time range.

    Examples:
        - get_stress_body_battery(date="2026-01-24") - Today's data
        - get_stress_body_battery(duration="7d") - Last week
    """
    start, end = get_time_range(date, start_date, end_date, duration)
    query, agg_info = build_select_query(
        measurement="StressIntraday",
        fields=["stressLevel", "bodyBattery"],
        start=start,
        end=end,
        aggregation=aggregation,
    )
    data = db.query(query)
    result = format_stress_body_battery(data, agg_info)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_activities(
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
    activity_type: str | None = None,
    limit: int = 20,
) -> str:
    """
    Get list of activities/workouts with summary metrics.

    Args:
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "30d", "3m", "1y" (from now)
        activity_type: Filter by type (e.g., "running", "cycling", "swimming")
        limit: Maximum number of activities to return (default 20)

    Returns:
        List of activities with name, type, distance, duration, calories,
        heart rate, pace, and location.

    Examples:
        - get_activities(duration="30d") - Last month's activities
        - get_activities(activity_type="running", limit=10) - Last 10 runs
        - get_activities(start_date="2026-01-01", end_date="2026-01-31")
    """
    start, end = None, None
    if duration or (start_date and end_date):
        start, end = get_time_range(None, start_date, end_date, duration)

    query = build_activities_query(start, end, activity_type, limit)
    data = db.query(query)
    result = format_activities_list(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_activity_details(activity_id: int) -> str:
    """
    Get comprehensive details for a specific activity including laps, cadence, training effect, and running dynamics.

    Args:
        activity_id: The activity ID (get this from get_activities)

    Returns:
        Full activity details including:
        - Basic info (name, type, date, location)
        - Distance and duration (elapsed vs moving time)
        - Speed/pace (average and max)
        - Heart rate (avg, max, and time in zones)
        - Calories (total and BMR)
        - Training effect (aerobic and anaerobic)
        - Running dynamics (vertical oscillation, ground contact time, step length, vertical ratio, running efficiency, step speed loss, step speed loss %) — running activities only
        - Respiration rate (min, avg, max — requires HRM 600 chest strap; only present from March 2026 onward)
        - Laps breakdown (distance, time, pace, HR, cadence, dynamics per lap, respiration rate per lap)
        - Cadence statistics (for running/cycling)

    Examples:
        - get_activity_details(activity_id=21651251107)
    """
    # Query ActivitySummary for main data (exclude "END" marker records)
    summary_query = f'''
        SELECT * FROM "ActivitySummary"
        WHERE "Activity_ID" = {activity_id} AND "activityType" != 'No Activity'
        ORDER BY time ASC LIMIT 1
    '''
    summary_data = db.query(summary_query)

    # Fallback: if no non-END record, try without filter
    if not summary_data:
        summary_query = f'''
            SELECT * FROM "ActivitySummary"
            WHERE "Activity_ID" = {activity_id}
            ORDER BY time ASC LIMIT 1
        '''
        summary_data = db.query(summary_query)

    if not summary_data:
        return json.dumps({"error": f"Activity {activity_id} not found"})

    summary = summary_data[0]

    # Query ActivityLap for lap details
    lap_query = f'''
        SELECT * FROM "ActivityLap"
        WHERE "Activity_ID" = {activity_id}
        ORDER BY time ASC
    '''
    laps_data = db.query(lap_query)

    # Query ActivitySession for training effect
    session_query = f'''
        SELECT * FROM "ActivitySession"
        WHERE "Activity_ID" = {activity_id}
        LIMIT 1
    '''
    session_data = db.query(session_query)
    session = session_data[0] if session_data else None

    # Query ActivityGPS for aggregate running dynamics (running efficiency, cadence)
    gps_agg_query = f'''
        SELECT MEAN("RunningEfficiency") AS "mean_running_efficiency",
               MEAN("Cadence") AS "mean_cadence"
        FROM "ActivityGPS"
        WHERE "Activity_ID" = {activity_id}
    '''
    gps_agg_data = db.query(gps_agg_query)
    gps_agg = gps_agg_data[0] if gps_agg_data else None

    result = format_activity_details(summary, laps_data, session, gps_agg)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_hrv(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
    include_intraday: bool = False,
) -> str:
    """
    Get Heart Rate Variability (HRV) data - a key recovery and readiness metric.

    Args:
        date: Single date in YYYY-MM-DD format
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d", "90d" (from now)
        include_intraday: If True, include per-minute HRV readings during sleep (default False)

    Returns:
        HRV data including:
        - Overnight average HRV (from sleep)
        - Trend analysis over time
        - Correlation with resting HR and sleep score
        - Optionally: intraday HRV readings during sleep

    HRV interpretation:
        - Higher HRV generally indicates better recovery and readiness
        - Look for consistent values; large drops may indicate stress/fatigue
        - Personal baseline matters more than absolute numbers

    Examples:
        - get_hrv(date="2026-01-24") - Last night's HRV
        - get_hrv(duration="30d") - 30-day HRV trend
        - get_hrv(duration="7d", include_intraday=True) - Week with detailed readings
    """
    from .queries import build_time_clause

    start, end = get_time_range(date, start_date, end_date, duration or "7d")
    time_clause = build_time_clause(start, end)

    # Get nightly HRV from SleepSummary
    daily_query = f'''
        SELECT "avgOvernightHrv", "restingHeartRate", "sleepScore"
        FROM "SleepSummary"
        WHERE {time_clause}
        ORDER BY time ASC
    '''
    daily_data = db.query(daily_query)

    # Optionally get intraday HRV
    intraday_data = None
    if include_intraday:
        intraday_query = f'''
            SELECT "hrvValue"
            FROM "HRV_Intraday"
            WHERE {time_clause}
            ORDER BY time ASC
            LIMIT 2000
        '''
        intraday_data = db.query(intraday_query)

    result = format_hrv_data(daily_data, intraday_data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_trends(
    metric: Literal["steps", "resting_hr", "sleep_score", "hrv", "stress", "weight"],
    duration: str = "90d",
    aggregation: AggregationType = "auto",
) -> str:
    """
    Get long-term trend analysis for a specific metric.

    Args:
        metric: One of "steps", "resting_hr", "sleep_score", "hrv", "stress", "weight"
        duration: Time period like "30d", "90d", "6m", "1y" (default "90d")
        aggregation: "auto" (default), "daily", "weekly", or "monthly"

    Returns:
        Trend analysis including min/max/avg, trend direction, and time series.

    Examples:
        - get_trends(metric="resting_hr", duration="90d") - 3-month HR trend
        - get_trends(metric="steps", duration="1y") - Yearly step trend
        - get_trends(metric="weight", duration="6m") - 6-month weight trend
    """
    start, end = get_time_range(duration=duration)

    # Map metric to measurement and field
    metric_map = {
        "steps": ("DailyStats", "totalSteps"),
        "resting_hr": ("DailyStats", "restingHeartRate"),
        "sleep_score": ("SleepSummary", "sleepScore"),
        "hrv": ("SleepSummary", "avgOvernightHrv"),
        "stress": ("DailyStats", "stressPercentage"),
        "weight": ("BodyComposition", "weight"),
    }

    if metric not in metric_map:
        return json.dumps({"error": f"Unknown metric: {metric}. Valid: {list(metric_map.keys())}"})

    measurement, field = metric_map[metric]

    # For daily measurements, always use daily aggregation at minimum
    if measurement in ("DailyStats", "SleepSummary", "BodyComposition"):
        query, agg_info = build_select_query(
            measurement=measurement,
            fields=[field],
            start=start,
            end=end,
            aggregation="raw",  # Already daily
        )
    else:
        query, agg_info = build_select_query(
            measurement=measurement,
            fields=[field],
            start=start,
            end=end,
            aggregation=aggregation,
        )

    data = db.query(query)

    if not data:
        return json.dumps({"error": f"No {metric} data available for the period"})

    values = [d.get(field) for d in data if d.get(field) is not None]

    # Special handling for weight (convert grams to kg)
    if metric == "weight":
        values = [v / 1000 for v in values]

    from .formatters import calculate_stats, calculate_trend, format_timestamp

    result = {
        "metric": metric,
        "period": {
            "start": format_timestamp(data[0].get("time", ""))[:10],
            "end": format_timestamp(data[-1].get("time", ""))[:10],
            "data_points": len(values),
        },
        "statistics": calculate_stats(values),
        "trend": calculate_trend(values),
        "data": [
            {
                "date": format_timestamp(d.get("time", ""))[:10],
                "value": round(d.get(field) / 1000, 1) if metric == "weight" else d.get(field),
            }
            for d in data if d.get(field) is not None
        ][:100],  # Limit output
    }

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_fitness_metrics() -> str:
    """
    Get current fitness metrics: VO2 max, fitness age, and race predictions.

    Returns:
        - VO2 max (ml/kg/min) with trend
        - Fitness age vs chronological age
        - Race predictions (5K, 10K, half marathon, marathon)

    Example:
        - get_fitness_metrics() - Current fitness snapshot
    """
    # Get recent data for each metric
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    start = now - timedelta(days=90)

    from .queries import build_time_clause

    time_clause = build_time_clause(start, now)

    vo2_query = f'SELECT "VO2_max_value" FROM "VO2_Max" WHERE {time_clause} ORDER BY time ASC'
    fitness_age_query = f'SELECT "fitnessAge", "chronologicalAge", "achievableFitnessAge" FROM "FitnessAge" WHERE {time_clause} ORDER BY time ASC'
    race_query = f'SELECT "time5K", "time10K", "timeHalfMarathon", "timeMarathon" FROM "RacePredictions" WHERE {time_clause} ORDER BY time ASC'

    vo2_data = db.query(vo2_query)
    fitness_age_data = db.query(fitness_age_query)
    race_data = db.query(race_query)

    result = format_fitness_metrics(vo2_data, fitness_age_data, race_data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_body_composition(
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get body composition data (weight tracking).

    Args:
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "30d", "90d", "6m" (from now)

    Returns:
        Weight readings in kg with trend analysis.

    Examples:
        - get_body_composition(duration="30d") - Last month
        - get_body_composition(duration="6m") - Last 6 months
    """
    start, end = get_time_range(None, start_date, end_date, duration or "90d")

    from .queries import build_time_clause

    time_clause = build_time_clause(start, end)
    query = f'SELECT "weight" FROM "BodyComposition" WHERE {time_clause} ORDER BY time ASC'

    data = db.query(query)
    result = format_body_composition(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_blood_pressure(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get blood pressure readings (systolic, diastolic, pulse).

    Args:
        date: Single date in YYYY-MM-DD format
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d", "3m" (from now)

    Returns:
        Blood pressure readings with systolic, diastolic, and pulse values.
        For multi-day queries, includes statistics and trends.

    Examples:
        - get_blood_pressure(date="2026-01-24") - Today's readings
        - get_blood_pressure(duration="30d") - Last month
        - get_blood_pressure(duration="6m") - 6-month trend
    """
    from .queries import build_time_clause

    start, end = get_time_range(date, start_date, end_date, duration or "30d")
    time_clause = build_time_clause(start, end)

    query = f'''
        SELECT "Systolic", "Diastolic", "Pulse"
        FROM "BloodPressure"
        WHERE {time_clause}
        ORDER BY time ASC
    '''
    data = db.query(query)
    result = format_blood_pressure(data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_training_status(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    duration: str | None = None,
) -> str:
    """
    Get training status and training readiness data (combined).

    Args:
        date: Single date in YYYY-MM-DD format
        start_date: Start of date range in YYYY-MM-DD format
        end_date: End of date range in YYYY-MM-DD format
        duration: Relative duration like "7d", "30d", "3m" (from now)

    Returns:
        Combined training data including:
        - Training status (productive/detraining/peaking/etc.)
        - Training load (weekly, acute, chronic, ACWR)
        - Training readiness score with factor breakdowns (sleep, HRV, recovery, stress, ACWR)
        - Recovery time

    Examples:
        - get_training_status(date="2026-01-24") - Today's training status
        - get_training_status(duration="7d") - Last week
        - get_training_status(duration="30d") - Monthly trend
    """
    from .queries import build_time_clause

    start, end = get_time_range(date, start_date, end_date, duration or "7d")
    time_clause = build_time_clause(start, end)

    status_query = f'''
        SELECT "trainingStatus", "trainingStatusFeedbackPhrase",
               "weeklyTrainingLoad", "fitnessTrend",
               "dailyTrainingLoadAcute", "dailyTrainingLoadChronic",
               "acwrPercent", "dailyAcuteChronicWorkloadRatio"
        FROM "TrainingStatus"
        WHERE {time_clause}
        ORDER BY time ASC
    '''

    readiness_query = f'''
        SELECT "score", "level", "recoveryTime", "acuteLoad",
               "sleepScore", "sleepScoreFactorPercent",
               "recoveryTimeFactorPercent", "acwrFactorPercent",
               "stressHistoryFactorPercent", "hrvFactorPercent"
        FROM "TrainingReadiness"
        WHERE {time_clause}
        ORDER BY time ASC
    '''

    status_data = db.query(status_query)
    readiness_data = db.query(readiness_query)
    result = format_training_status(status_data, readiness_data)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def query_measurement(
    measurement: str,
    fields: str = "*",
    duration: str = "7d",
    aggregation: AggregationType = "auto",
    where_clause: str | None = None,
    limit: int = 1000,
) -> str:
    """
    Advanced: Query any InfluxDB measurement directly.

    Args:
        measurement: Measurement name (e.g., "HeartRateIntraday", "SleepIntraday")
        fields: Comma-separated field names or "*" for all
        duration: Time period like "7d", "30d", "3m"
        aggregation: "auto", "raw", "hourly", "daily", "weekly"
        where_clause: Additional WHERE conditions (e.g., "activityType = 'running'")
        limit: Maximum rows to return (default 1000)

    Returns:
        Raw query results as JSON.

    Available measurements:
        - DailyStats, SleepSummary, SleepIntraday
        - HeartRateIntraday, StepsIntraday, StressIntraday
        - BodyBatteryIntraday, BreathingRateIntraday, HRV_Intraday
        - ActivitySummary, ActivityGPS, ActivityLap
        - BodyComposition, VO2_Max, FitnessAge, RacePredictions
        - BloodPressure, TrainingStatus, TrainingReadiness

    Examples:
        - query_measurement(measurement="StepsIntraday", duration="1d")
        - query_measurement(measurement="ActivityGPS", where_clause="Activity_ID = 12345")
    """
    start, end = get_time_range(duration=duration)

    field_list = [f.strip() for f in fields.split(",")] if fields != "*" else "*"

    query, agg_info = build_select_query(
        measurement=measurement,
        fields=field_list,
        start=start,
        end=end,
        aggregation=aggregation,
        where_extra=where_clause,
        limit=limit,
    )

    data = db.query(query)

    result = {
        "measurement": measurement,
        "query": query,
        "aggregation": agg_info.get("description"),
        "row_count": len(data),
        "data": data[:100] if len(data) > 100 else data,
        "truncated": len(data) > 100,
    }

    return json.dumps(result, indent=2, default=str)


# Resources for schema discovery
@mcp.resource("garmin://schema/measurements")
def get_schema_measurements() -> str:
    """List all available measurements in the database."""
    measurements = db.get_measurements()
    return json.dumps({"measurements": measurements}, indent=2)


@mcp.resource("garmin://schema/{measurement}")
def get_schema_fields(measurement: str) -> str:
    """Get field definitions for a specific measurement."""
    fields = db.get_field_keys(measurement)
    return json.dumps({"measurement": measurement, "fields": fields}, indent=2)


@mcp.resource("garmin://status")
def get_status() -> str:
    """Get database connection status and last sync time."""
    try:
        connected = db.test_connection()

        # Get last data point
        last_sync = db.query('SELECT * FROM "DailyStats" ORDER BY time DESC LIMIT 1')
        last_time = last_sync[0].get("time") if last_sync else None

        return json.dumps({
            "connected": connected,
            "database": db.database,
            "host": db.host,
            "last_data": last_time,
        }, indent=2)
    except Exception as e:
        return json.dumps({"connected": False, "error": str(e)}, indent=2)


class _BearerAuthMiddleware:
    """ASGI middleware that enforces bearer token authentication."""

    def __init__(self, app, token):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if not hmac.compare_digest(auth_header, f"Bearer {self.token}"):
                from starlette.responses import JSONResponse

                response = JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def main():
    """Run the MCP server."""
    transport = os.environ.get("GARMIN_MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        mcp.run()
    elif transport == "streamable-http":
        import anyio
        import uvicorn

        async def _serve():
            port = int(os.environ.get("GARMIN_MCP_HTTP_PORT", "8090"))
            auth_token = os.environ.get("GARMIN_MCP_AUTH_TOKEN")
            app = mcp.streamable_http_app()
            if auth_token:
                app = _BearerAuthMiddleware(app, auth_token)
            config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()

        anyio.run(_serve)
    else:
        raise ValueError(
            f"Unknown transport: {transport}. Use 'stdio' or 'streamable-http'."
        )


if __name__ == "__main__":
    main()
