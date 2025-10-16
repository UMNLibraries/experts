from pydantic import BaseModel, computed_field


class Rectangle(BaseModel):
    width: int
    length: int

    @computed_field(return_type=int)
    @property
    def area(self) -> int:
        return self.width * self.length

        # Generates a warning. See below.
        #return 'bogus'

# If we return a string instead of an int, the following line generates
# this warning:
# /home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pydantic/main.py:463: UserWarning: Pydantic serializer warnings:
#  PydanticSerializationUnexpectedValue(Expected `int` - serialized value may not be as expected [input_value='bogus', input_type=str])
#  return self.__pydantic_serializer__.to_python(
# {'width': 3, 'length': 2, 'area': 'bogus'}
#
# If we comment out the following line, we get no warning.
print(Rectangle(width=3, length=2).model_dump())
