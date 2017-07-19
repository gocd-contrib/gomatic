class CommonEqualityMixin(object):
    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(str(self))

    def __repr__(self):
        keys = self.__dict__.keys()
        keys.sort()
        return "Some %s" % self.__class__ + " Fields[" + (
            ", ".join([str(k) + ":" + str(self.__dict__[k]) for k in keys]) + "]")
