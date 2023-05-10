#if defined(_MSC_VER) && (_MSC_VER >= 1600)
#pragma execution_character_set("utf-8")
#endif

#ifndef STDAFX_H
#define STDAFX_H

#define Q_PROPERTY_AUTO(TYPE, M)                                                                                       \
  Q_PROPERTY(TYPE M MEMBER _##M NOTIFY M##Changed)                                                                     \
public:                                                                                                                \
  Q_SIGNAL void M##Changed();                                                                                          \
  void M(TYPE in_##M)                                                                                                  \
  {                                                                                                                    \
    _##M = in_##M;                                                                                                     \
    Q_EMIT M##Changed();                                                                                               \
  }                                                                                                                    \
  TYPE M()                                                                                                             \
  {                                                                                                                    \
    return _##M;                                                                                                       \
  }                                                                                                                    \
                                                                                                                       \
private:                                                                                                               \
  TYPE _##M;

#endif  // STDAFX_H
