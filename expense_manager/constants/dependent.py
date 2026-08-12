from enum import Enum


class Relationship(str, Enum):
	SON = "Son"
	DAUGHTER = "Daughter"
	BROTHER = "Brother"
	SISTER = "Sister"
	SPOUSE = "Spouse"
	PARENT = "Parent"
	FRIEND = "Friend"
	OTHER = "Other"
